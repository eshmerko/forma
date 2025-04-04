from django.shortcuts import get_object_or_404, render, redirect
from django.forms import modelformset_factory
from .forms import CompanyForms, ZakupkiForms, LotsForms, ClassifikatorForm, SearchForm
from .models import Company, PredmetZakupki, Lots, Clasifikator
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import requests
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from django.views.decorators.csrf import csrf_exempt
from mistralai import Mistral
import logging
import json
from collections import Counter
import time

import os
from datetime import datetime, timedelta
from django.conf import settings

from django.contrib.auth.decorators import user_passes_test

from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from bs4 import BeautifulSoup
import pandas as pd
from django.templatetags.static import static


# Настройка API
API_KEY = "JQrFsd8FA2PusEUG6eXKce5Zo1y0mjDQ"
MODEL = "mistral-large-latest"
client = Mistral(api_key=API_KEY)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            user_message = request.POST.get('message')
            if not user_message or not user_message.strip():
                return JsonResponse({"error": "Message cannot be empty"}, status=400)

            # Системный промпт для задания контекста беседы
            system_prompt = {
                "role": "system",
                "content": "Вы являетесь помощником, который помогает с закупками в Республике Беларусь. Вы соблюдаете законодательство в области закупок в Республике Беларусь и только. Отвечайте четко и по существу."
            }

            # Создание запроса с системным промптом
            chat_response = client.chat.complete(
                model=MODEL,
                messages=[
                    system_prompt,  # Добавление системного промпта
                    {"role": "user", "content": user_message.strip()}
                ]
            )
            response_content = chat_response.choices[0].message.content

            # Преобразование текста в формат Markdown или HTML (если необходимо)
            formatted_response = format_response(response_content)

            return JsonResponse({"response": formatted_response})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

def format_response(text):
    """
    Преобразует текст в читаемый вид, заменяя Markdown-синтаксис на переносы строк.
    """
    # Заменяем Markdown-форматирование на перенос строки
    text = text.replace("**", "\n").replace("*", "")  # Убираем неиспользуемый Markdown
    # Убираем лишние пробелы, если есть
    return text.strip()

@login_required
@require_http_methods(["GET"])
def menu(request):
    # Получаем данные о курсах валют
    currency_ids = [431, 451, 456]  # Пример ID валют
    currency_data = []

    for currency_id in currency_ids:
        cache_key = f"currency_{currency_id}"
        data = cache.get(cache_key)

        if not data:
            url = f"https://api.nbrb.by/exrates/rates/{currency_id}"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                cache.set(cache_key, data, timeout=60*60)  # Кэшируем на 1 час
            else:
                # Логируем ошибку или уведомляем пользователя
                continue

        currency_data.append({
            "name": data.get("Cur_Name"),
            "rate": data.get("Cur_OfficialRate"),
            "unit": data.get("Cur_Scale")
        })

    # Получаем данные о ставке рефинансирования
    current_date = datetime.now().strftime("%Y-%m-%d")  # Текущая дата в формате YYYY-MM-DD
    refinancing_rate_url = f"https://www.nbrb.by/api/refinancingrate?ondate={current_date}"
    refinancing_rate_response = requests.get(refinancing_rate_url)

    refinancing_rate = None  # По умолчанию ставка неизвестна

    if refinancing_rate_response.status_code == 200:
        refinancing_rate_data = refinancing_rate_response.json()
        # Проверяем, что данные есть и это список
        if isinstance(refinancing_rate_data, list) and len(refinancing_rate_data) > 0:
            # Берем первый элемент списка
            refinancing_rate = refinancing_rate_data[0].get("Value")

    return render(request, 'menu.html', {
        'currency_data': currency_data,  # Данные о курсах валют
        'refinancing_rate': refinancing_rate,  # Ставка рефинансирования
    })

def my_view(request):
    if request.method == 'POST':
        unp = request.POST.get('unp')

        api_url1 = f'http://egr.gov.by/api/v2/egr/getJurNamesByRegNum/{unp}'
        response1 = requests.get(api_url1)

        api_url2 = f'http://egr.gov.by/api/v2/egr/getAddressByRegNum/{unp}'
        response2 = requests.get(api_url2)

        if response1.status_code == 200 and response2.status_code == 200:
            api_data = {
                'endpoint1': response1.json(),
                'endpoint2': response2.json()
            }
            return JsonResponse(api_data, safe=False)
        else:
            error_data = {
                'error1': f'Ошибка получения данных. Вам придется заполнить сведения в ручную.',
                'error2': f'Нам очень жаль, но сервис ЕГР не смог выполнить ваш запрос.'
            }
            return JsonResponse(error_data, status=400)

    return render(request, 'regforma.html')

# View для отображения информации о закупке
def zakupki_detail(request, zakupki_id):
    zakupka = get_object_or_404(PredmetZakupki, id=zakupki_id)
    company = zakupka.company
    lots = Lots.objects.filter(zakupki=zakupka)

    return render(request, 'zakupki_detail.html', {
        'zakupka': zakupka,
        'company': company,
        'lots': lots,
    })

# Обновленный regforma с редиректом на страницу с деталями
def regforma(request):
    LotsFormSet = modelformset_factory(Lots, form=LotsForms, extra=1)
    
    if request.method == 'POST':
        company_form = CompanyForms(request.POST)
        zakupki_form = ZakupkiForms(request.POST)
        formset = LotsFormSet(request.POST)
        
        if company_form.is_valid() and zakupki_form.is_valid() and formset.is_valid():
            company = company_form.save(commit=False)
            company_instance, created = Company.objects.get_or_create(
                name=company.name,
                unp=company.unp,
                defaults={'adress': company.adress, 'author': request.user}
            )
            
            zakupki = zakupki_form.save(commit=False)
            zakupki.company = company_instance
            zakupki_instance, created = PredmetZakupki.objects.get_or_create(
                nomer_dogovora=zakupki.nomer_dogovora,
                company=company_instance,
                defaults={
                    'data_dogovora': zakupki.data_dogovora, 
                    'price_full': zakupki.price_full, 
                    'vid_zakupki': zakupki.vid_zakupki
                }
            )

            for form in formset:
                lot = form.save(commit=False)
                lot.zakupki = zakupki_instance
                lot.save()

            return redirect('zakupki_detail', zakupki_id=zakupki_instance.id)
    
    else:
        company_form = CompanyForms()
        zakupki_form = ZakupkiForms()
        formset = LotsFormSet(queryset=Lots.objects.none())
    
    return render(request, 'regforma.html', {
        'company_form': company_form,
        'zakupki_form': zakupki_form,
        'formset': formset,
    })

from django.shortcuts import render
from django.contrib.auth.models import User
from .models import Company, PredmetZakupki, Lots
from django.db.models import Q

def filter_view(request):
    companies = Company.objects.all().prefetch_related('zakupki__lots')
    zakupki_list = PredmetZakupki.objects.all()
    lots_list = Lots.objects.all()
    selected_filters = {}

    # Получаем уникальных авторов и страны для фильтров
    authors = User.objects.distinct()
    countries = Lots.objects.values_list('country', flat=True).distinct()

    if request.method == 'POST':
        # Фильтр по компании
        company_id = request.POST.get('company_id')
        if company_id:
            zakupki_list = zakupki_list.filter(company_id=company_id)
            selected_filters['company_id'] = company_id

        # Фильтр по номеру договора
        nomer_dogovora = request.POST.get('nomer_dogovora')
        if nomer_dogovora:
            zakupki_list = zakupki_list.filter(nomer_dogovora__icontains=nomer_dogovora)
            selected_filters['nomer_dogovora'] = nomer_dogovora

        # Фильтр по виду закупки
        vid_zakupki = request.POST.get('vid_zakupki')
        if vid_zakupki:
            zakupki_list = zakupki_list.filter(vid_zakupki=vid_zakupki)
            selected_filters['vid_zakupki'] = vid_zakupki

        # Фильтр по автору
        author_id = request.POST.get('author')
        if author_id:
            zakupki_list = zakupki_list.filter(company__author_id=author_id)
            selected_filters['author'] = author_id

        # Фильтр по стране
        country = request.POST.get('country')
        if country:
            lots_list = lots_list.filter(country=country)
            selected_filters['country'] = country

        # Фильтр по дате начала
        start_date = request.POST.get('start_date')
        if start_date:
            zakupki_list = zakupki_list.filter(data_dogovora__gte=start_date)
            selected_filters['start_date'] = start_date

        # Фильтр по дате окончания
        end_date = request.POST.get('end_date')
        if end_date:
            zakupki_list = zakupki_list.filter(data_dogovora__lte=end_date)
            selected_filters['end_date'] = end_date

        # Фильтрация лотов по выбранным закупкам
        lots_list = Lots.objects.filter(zakupki__in=zakupki_list)

    return render(request, 'filter.html', {
        'companies': companies,
        'zakupki_list': zakupki_list,
        'lots_list': lots_list,
        'selected_filters': selected_filters,
        'authors': authors,
        'countries': countries,
    })

def calculate_price(request):
    if request.method == 'POST':
        total_price = request.POST.get('total_price', 0.00)
        return JsonResponse({'total_price': total_price})
    
@login_required
def table(request):
    # Если пользователь — суперпользователь, показываем все закупки
    if request.user.is_superuser:
        companies = Company.objects.prefetch_related('zakupki__lots').all()
    else:
        # Иначе показываем только закупки, созданные текущим пользователем
        companies = Company.objects.filter(author=request.user).prefetch_related('zakupki__lots')
    
    return render(request, 'table.html', {'companies': companies})


@login_required
def export_to_excel(request):
    # Создаем книгу и активный лист
    wb = Workbook()
    ws = wb.active
    ws.title = "Компании и закупки"
    
    # Заголовки таблицы
    headers = [
        "№", "Название организации", "Юридический адрес", "УНП", "Автор",
        "Вид процедуры закупки", "Номер договора", "Дата заключения договора", "Общая стоимость договора",
        "Номер лота", "Код ОКРБ", "Предмет закупки", "Количество", "Единица измерения", "Страна", "Стоимость лота"
    ]
    ws.append(headers)
    
    # Заполняем таблицу данными
    companies = Company.objects.prefetch_related(
        'zakupki__lots'  # Используем правильные имена для related_name
    ).all()
    
    for company_index, company in enumerate(companies, start=1):
        for zakupka in company.zakupki.all():
            for lot in zakupka.lots.all():
                ws.append([
                    company_index,
                    company.name,
                    company.adress,
                    company.unp,
                    company.author.username,
                    zakupka.vid_zakupki,
                    zakupka.nomer_dogovora,
                    zakupka.data_dogovora,
                    zakupka.price_full,
                    lot.number_lot,
                    lot.cod_okrb,
                    lot.predmet_zakupki,
                    lot.unit,
                    lot.ed_izmer,
                    lot.country,
                    lot.price_lot,
                ])
    
    # Устанавливаем HTTP-заголовки для скачивания
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=companies_data.xlsx'
    wb.save(response)
    return response

def draw_wrapped_text(p, text, x, y, max_width):
    """
    Отрисовывает текст, автоматически перенося строки, если текст превышает max_width.
    """
    lines = []
    words = text.split()
    line = ""

    for word in words:
        # Проверяем, влезает ли слово в текущую строку
        if pdfmetrics.stringWidth(line + " " + word, p._fontname, p._fontsize) <= max_width:
            line += " " + word if line else word
        else:
            lines.append(line)
            line = word
    lines.append(line)

    for line in lines:
        p.drawString(x, y, line)
        y -= 20  # Смещение по вертикали на следующую строку
    return y

def generate_pdf(request, zakupki_id):
    # Получаем информацию о закупке
    zakupka = get_object_or_404(PredmetZakupki, id=zakupki_id)
    company = zakupka.company
    lots = Lots.objects.filter(zakupki=zakupka)

    # Создаем HttpResponse с типом 'application/pdf'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="zakupka_{zakupki_id}.pdf"'

    # Создаем PDF с помощью ReportLab
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4  # размеры страницы PDF

    # Подключаем шрифт
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'regforma/fonts/DejaVuSans.ttf'))
        p.setFont("DejaVuSans", 13)
    except Exception as e:
        p.setFont("Helvetica", 13)  # Резервный шрифт
        p.drawString(70, 800, "Ошибка загрузки шрифта: используем стандартный.")

    # Заголовок
    p.setFont("DejaVuSans", 16)
    p.drawString(70, 780, f"Закупку провел: {request.user.first_name} {request.user.last_name}")
    p.drawRightString(width - 70, 780, f"Закупка № {zakupka.id}")

    # Основная информация
    p.setFont("DejaVuSans", 14)
    y = 750
    y = draw_wrapped_text(p, f"Дата регистрации в БД: {zakupka.data_creator_zakupki.strftime('%d.%m.%Y')}", 70, y, width - 140)
    y = draw_wrapped_text(p, f"Вид закупки: {zakupka.vid_zakupki}", 70, y, width - 140)
    y = draw_wrapped_text(p, f"Название организации: {company.name}", 70, y, width - 140)
    y = draw_wrapped_text(p, f"Юридический адрес: {company.adress}", 70, y, width - 140)
    y = draw_wrapped_text(p, f"Номер договора: {zakupka.nomer_dogovora} от {zakupka.data_dogovora.strftime('%d.%m.%Y')}", 70, y, width - 140)
    y = draw_wrapped_text(p, f"Сумма контракта: {zakupka.price_full} руб.", 70, y, width - 140)

    # Лоты
    y -= 20  # небольшое отступление перед блоком лотов
    for lot in lots:
        y = draw_wrapped_text(p, f"Лот № {lot.number_lot}: {lot.predmet_zakupki}", 70, y, width - 140)
        y = draw_wrapped_text(p, f"  Код ОКРБ: {lot.cod_okrb}, Количество: {lot.unit} {lot.ed_izmer}, Страна: {lot.country}", 70, y, width - 140)
        y = draw_wrapped_text(p, f"  Стоимость: {lot.price_lot} руб.", 70, y, width - 140)
        y -= 20  # расстояние между лотами
        if y < 100:  # Переход на новую страницу при нехватке места
            p.showPage()
            p.setFont("DejaVuSans", 13)
            y = 780

    # Подписи
    p.setFont("DejaVuSans", 16)
    #p.drawString(70, y - 20, f"Закупку провел: {request.user.first_name} {request.user.last_name}")
    p.setFont("DejaVuSans", 13)
    p.drawString(70, y - 50, f"Проверил: ______________________ Е.Л.Шмерко ")

    # Сохраняем PDF
    p.showPage()
    p.save()

    return response

def video_page(request):
    return render(request, 'video.html')

def classifikator(request):
    return render(request, 'classifikator.html')  # Шаблон для отображения страницы

def classifikatorajax(request):
    form = ClassifikatorForm(request.GET)
    
    if form.is_valid():
        code = form.cleaned_data.get('code')  # Получаем данные из формы
        name = form.cleaned_data.get('name')

        # Выполняем фильтрацию по коду ОКРБ и названию товара
        queryset = Clasifikator.objects.all()

        if code:
            queryset = queryset.filter(code__icontains=code)
        if name:
            queryset = queryset.filter(name__icontains=name)

        # Подготовим результаты для возврата в формате JSON
        results = list(queryset.values('id', 'code', 'name'))
        return JsonResponse({'results': results})
    
    # Если форма не валидна, вернуть пустой результат
    return JsonResponse({'results': []})

# Поиск кода ОКРБ на Gias.by
def extract_codeOKPB(data):
    codeOKPB_list = []
    for purchase in data:
        if "lots" in purchase:
            for lot in purchase["lots"]:
                if "codeOKPB" in lot:
                    codeOKPB_list.extend(lot["codeOKPB"])
    return codeOKPB_list

def calculate_percentages(codeOKPB_list):
    total_count = len(codeOKPB_list)
    if total_count == 0:
        return {}
    counter = Counter(codeOKPB_list)
    percentages = {code: (count / total_count) * 100 for code, count in counter.items()}
    return percentages

from django.http import JsonResponse

def search_view(request):
    if request.method == 'POST':
        
        form = SearchForm(request.POST)
        if form.is_valid():
            contextTextSearch = form.cleaned_data['contextTextSearch']
            all_purchase_data = []
            url = "https://www.gias.by/search/api/v1/search/purchases"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
            }

            total_pages = 3  # Количество страниц
            page_size = 10  # Количество записей на странице
            total_requests = total_pages * page_size  # Общее количество запросов
            request.session['progress'] = 0  # Инициализация прогресса
            request.session['total_requests'] = total_requests  # Сохраняем общее количество запросов

            for page in range(total_pages):
                payload = {
                    "contextTextSearch": contextTextSearch,
                    "page": page,
                    "pageSize": page_size,
                    "sortField": "dtCreate",
                    "sortOrder": "DESC"
                }
                time.sleep(1)  # Задержка между запросами

                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        for purchase in data.get("content", []):
                            sum_lot = purchase.get("sumLot", {})
                            uuid = sum_lot.get("uuid")
                            if uuid:
                                purchase_url = f"https://gias.by/purchase/api/v1/purchase/{uuid}"
                                purchase_response = requests.get(purchase_url)
                                if purchase_response.status_code == 200:
                                    purchase_data = purchase_response.json()
                                    all_purchase_data.append(purchase_data)

                                # Обновляем прогресс после каждого запроса
                                request.session['progress'] += 1
                                request.session.save()
                    else:
                        print(f"Ошибка на странице {page + 1}: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"Ошибка подключения: {e}")

            # Сохраняем данные в файл (опционально)
            with open('json/all_purchases.json', 'w', encoding='utf-8') as f:
                json.dump(all_purchase_data, f, ensure_ascii=False, indent=4)

            # Фильтруем данные по ключевому слову в "title"
            filtered_data = [
                purchase for purchase in all_purchase_data
                if contextTextSearch.lower() in purchase.get("title", "").lower()
            ]

            # Извлекаем codeOKPB и считаем проценты
            codeOKPB_list = extract_codeOKPB(filtered_data)
            percentages = calculate_percentages(codeOKPB_list)

            # Сортируем проценты от большего к меньшему
            sorted_percentages = dict(sorted(percentages.items(), key=lambda item: item[1], reverse=True))

            # Загружаем данные о видах экономической деятельности
            activities_data = load_economic_activities()
            activities_dict = {activity["code"]: activity["name"] for activity in activities_data}

            # Находим названия для каждого codeOKPB
            economic_activities = {}
            for code in sorted_percentages.keys():
                economic_activities[code] = activities_dict.get(code, "Нет данных")

            # Сбрасываем прогресс после завершения
            request.session['progress'] = total_requests
            request.session.save()

            # Если запрос выполняется через AJAX, возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'percentages': sorted_percentages,
                    'search_term': contextTextSearch,
                    'economic_activities': economic_activities
                })

            # Иначе возвращаем HTML
            return render(request, 'search_form.html', {
                'form': form,
                'percentages': sorted_percentages,
                'search_term': contextTextSearch,
                'economic_activities': economic_activities
            })
    else:
        form = SearchForm()

    return render(request, 'search_form.html', {'form': form})

# Новый view для получения прогресса
def get_progress(request):
    try:
        progress = request.session.get('progress', 0)
        total_requests = request.session.get('total_requests', 1)
        percent = (progress / total_requests) * 100
        return JsonResponse({'progress': min(percent, 100)})  # Не больше 100%
    except Exception as e:
        return JsonResponse({'progress': 0})

# Путь к JSON-файлу
JSON_FILE_PATH = os.path.join(settings.BASE_DIR, 'json', 'economic_activities.json')

def update_economic_activities():
    """
    Обновляет данные о видах экономической деятельности и сохраняет их в JSON-файл.
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get("https://gias.by/directory/api/v1/economic_activity", headers=headers)
        if response.status_code == 200:
            activities_data = response.json()
            # Сохраняем данные в JSON-файл
            with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(activities_data, f, ensure_ascii=False, indent=4)
            print("Данные успешно обновлены.")
        else:
            print(f"Ошибка при запросе видов экономической деятельности: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка подключения: {e}")

def load_economic_activities():
    """
    Загружает данные о видах экономической деятельности из JSON-файла.
    Если файл не существует или устарел, обновляет его.
    """
    if not os.path.exists(JSON_FILE_PATH):
        # Если файл не существует, создаем его
        update_economic_activities()

    # Проверяем дату последнего обновления файла
    last_modified = datetime.fromtimestamp(os.path.getmtime(JSON_FILE_PATH))
    if datetime.now() - last_modified > timedelta(days=30):  # Обновляем раз в месяц
        update_economic_activities()

    # Загружаем данные из файла
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def download_economic_activities(request):
    """
    Представление для скачивания JSON-файла.
    """
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/json')
            response['Content-Disposition'] = 'attachment; filename="economic_activities.json"'
            return response
    else:
        return HttpResponse("Файл не найден.", status=404)
    


@user_passes_test(lambda u: u.is_superuser)
def export_all_to_excel(request):
    # Создаем книгу и активный лист
    wb = Workbook()
    ws = wb.active
    ws.title = "Все закупки"
    
    # Заголовки таблицы
    headers = [
        "№", "Название организации", "Юридический адрес", "УНП", "Автор",
        "Вид процедуры закупки", "Номер договора", "Дата заключения договора", "Общая стоимость договора",
        "Номер лота", "Код ОКРБ", "Предмет закупки", "Количество", "Единица измерения", "Страна", "Стоимость лота"
    ]
    ws.append(headers)
    
    # Заполняем таблицу данными
    companies = Company.objects.prefetch_related('zakupki__lots').all()
    
    for company_index, company in enumerate(companies, start=1):
        for zakupka in company.zakupki.all():
            for lot in zakupka.lots.all():
                ws.append([
                    company_index,
                    company.name,
                    company.adress,
                    company.unp,
                    company.author.username,
                    zakupka.vid_zakupki,
                    zakupka.nomer_dogovora,
                    zakupka.data_dogovora,
                    zakupka.price_full,
                    lot.number_lot,
                    lot.cod_okrb,
                    lot.predmet_zakupki,
                    lot.unit,
                    lot.ed_izmer,
                    lot.country,
                    lot.price_lot,
                ])
    
    # Устанавливаем HTTP-заголовки для скачивания
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=all_purchases.xlsx'
    wb.save(response)
    return response

def parser(index_list):
    start_time = time.time()  # Начало выполнения функции
    user_agent = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0.'}
    all_data = []  # Список для хранения данных от всех кодов
    all_links = []  # Список для хранения всех ссылок

    for index in index_list:
        url = f'https://icetrade.by/producers/search?company=&find_type=1&type_company%5B1%5D=1&type_company%5B2%5D=1&num=&unp=&uraddress=&register_from=&register_to=&product=&okrb_2012={index}&sort=num%3Aasc&sbm=1&onPage=100'
        
        # Запрос к главной странице
        start_request_time = time.time()
        r = requests.get(url, headers=user_agent, verify=False)
        soup = BeautifulSoup(r.text, 'lxml')
        request_time = time.time() - start_request_time
        print(f"Время на выполнение запроса к {url}: {request_time:.2f} секунд")
        
        # Поиск ссылок
        el = soup.find('table', class_='auctions').find_all('a')
        links = list(set([i.get('href') for i in el]))
        all_links.extend(links)  # Добавляем ссылки в общий список

        # Парсинг данных по каждой ссылке
        for url_1 in links:
            start_inner_request_time = time.time()
            rq = requests.get(url_1, headers=user_agent, verify=False)
            time.sleep(3)  # Эмуляция ожидания
            soup = BeautifulSoup(rq.text, 'lxml')
            inner_request_time = time.time() - start_inner_request_time
            print(f"Время на выполнение запроса к {url_1}: {inner_request_time:.2f} секунд")
            
            # Извлечение данных
            organiz = soup.find('table', class_='w100').find(text='Организация').find_next().text
            adres = soup.find('table', class_='w100').find(text='Юридический адрес').find_next().text
            unp = soup.find('table', class_='w100').find(text='УНП организации').find_next().text
            telefon = soup.find('table', class_='w100').find(text='Телефон').find_next().text
            email = soup.find('table', class_='w100').find(text='email').find_next().text
            
            all_data.append([organiz, adres, unp, telefon, email])

    # Создание и сохранение DataFrame
    start_dataframe_time = time.time()
    header = ['Организация', 'Юридический адрес', 'УНП организации', 'Телефон', 'email']
    df = pd.DataFrame(all_data, columns=header)
    df.drop_duplicates(subset=None, inplace=True)

    organizations = ', '.join(df['Организация'].dropna().unique())
    emails = '; '.join(df['email'].dropna().unique())

    summary_row = pd.DataFrame({
        'Организация': [f"Итого: {organizations}"],
        'Юридический адрес': [''],
        'УНП организации': [''],
        'Телефон': [''],
        'email': [f"Итого: {emails}"]
    })

    df = pd.concat([df, summary_row], ignore_index=True)
    
    # Сохранение CSV-файла
    csv_output_file = os.path.join('static', 'csv', 'combined_results.csv')
    df.to_csv(csv_output_file, sep=';', encoding='utf-8', index=False)
    
    # Сохранение ссылок в файл
    links_output_file = os.path.join('static', 'csv', 'links.txt')
    with open(links_output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(all_links))
    
    dataframe_time = time.time() - start_dataframe_time
    print(f"Время на создание и сохранение DataFrame: {dataframe_time:.2f} секунд")
    
    # Общее время выполнения функции
    total_time = time.time() - start_time
    print(f"Общее время выполнения функции: {total_time:.2f} секунд")
    
    return csv_output_file, links_output_file  # Возвращаем пути к CSV и links.txt

def parser_form(request):
    csv_file = None
    links_file = None
    if request.method == 'POST':
        index_list = request.POST.getlist('index[]')  # Получаем список кодов
        if index_list:
            csv_file, links_file = parser(index_list)  # Вызов функции parser
            csv_file = static('csv/combined_results.csv')  # Использование Django шаблонного тега static
            links_file = static('csv/links.txt')  # Путь к файлу со ссылками

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'csv_file': csv_file,
                'links_file': links_file
            })

    return render(request, 'parser_form.html', {'csv_file': csv_file, 'links_file': links_file})

def statistics_view(request):
    cod_okrb_filter = request.GET.get('cod_okrb', '').strip()
    
    stats = Lots.objects.all()
    
    if cod_okrb_filter:
        stats = stats.filter(cod_okrb__icontains=cod_okrb_filter)
    
    stats = stats.values('cod_okrb').annotate(
        total_price=Sum('price_lot')
    ).order_by('cod_okrb')
    
    for item in stats:
        bw = item['total_price'] / 42
        item['bw_value'] = f"{bw:,.2f} БВ".replace(',', ' ')
        item['warnings'] = []
        item['status_class'] = 'success'
        
        if bw >= 1000:
            item['warnings'].append({
                'text': "❌ Только конкурентная процедура закупки!", 
                'class': 'danger'
            })
            item['status_class'] = 'danger'
        elif bw > 15:
            remaining = 1000 - bw
            if remaining > 0:
                item['warnings'].append({
                    'text': f"⚠️ Доступно для 'Сравнительной таблицы': {remaining:,.2f} БВ",
                    'class': 'warning'
                })
            else:
                item['warnings'].append({
                    'text': "⛔ Закупка по 'Сравнительной таблице' запрещена!",
                    'class': 'danger'
                })
            
            # Яркое выделение запрета упрощенной процедуры
            item['warnings'].append({
                'text': "🚫 ЗАПРЕЩЕНО: Упрощенная процедура",
                'class': 'danger blink-highlight'
            })
            item['status_class'] = 'warning'
        else:
            item['warnings'].append({
                'text': "✅ Нет ограничений",
                'class': 'success'
            })
    
    return render(request, 'statistics.html', {
        'stats': stats,
        'current_filter': cod_okrb_filter
    })