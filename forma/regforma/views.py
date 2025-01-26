from django.shortcuts import get_object_or_404, render, redirect
from django.forms import modelformset_factory
from .forms import CompanyForms, ZakupkiForms, LotsForms, ClassifikatorForm, SearchForm
from .models import Company, PredmetZakupki, Lots, Clasifikator
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
def menu(request):
    return render(request, 'menu.html')

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
                defaults={'adress': company.adress}
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

def filter_view(request):
    companies = Company.objects.all().prefetch_related('zakupki__lots')  # Предварительная загрузка
    zakupki_list = PredmetZakupki.objects.all()  # Все закупки
    lots_list = Lots.objects.all()  # Все лоты
    selected_filters = {}  # Хранение выбранных фильтров для отображения

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

        # Фильтрация лотов по выбранным закупкам
        lots_list = Lots.objects.filter(zakupki__in=zakupki_list)

        # Фильтр по стране
        country = request.POST.get('country')
        if country:
            lots_list = lots_list.filter(country=country)
            selected_filters['country'] = country

        # Фильтр по единице измерения
        ed_izmer = request.POST.get('ed_izmer')
        if ed_izmer:
            lots_list = lots_list.filter(ed_izmer=ed_izmer)
            selected_filters['ed_izmer'] = ed_izmer

    return render(request, 'filter.html', {
        'companies': companies,
        'zakupki_list': zakupki_list,
        'lots_list': lots_list,
        'selected_filters': selected_filters,
    })
def calculate_price(request):
    if request.method == 'POST':
        total_price = request.POST.get('total_price', 0.00)
        return JsonResponse({'total_price': total_price})
    
@login_required
def table(request):
    companies = Company.objects.prefetch_related('zakupki__lots')  # Предзагрузка связанных данных
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
    
    