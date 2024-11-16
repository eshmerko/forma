from django.shortcuts import get_object_or_404, render, redirect
from django.forms import modelformset_factory
from .forms import CompanyForms, ZakupkiForms, LotsForms
from .models import Company, PredmetZakupki, Lots
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import requests
from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

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
    companies = Company.objects.all()  # Получаем все компании
    selected_company = None
    selected_nomer_dogovora = None
    zakupki_list = []  # Список для хранения закупок и связанных лотов
    lots_list = []  # Список для хранения лотов

    if request.method == 'POST':
        company_id = request.POST.get('company_id')  # Получаем выбранную компанию
        selected_company = Company.objects.get(id=company_id) if company_id else None

        if selected_company:
            zakupki_list = PredmetZakupki.objects.filter(company=selected_company)  # Получаем закупки для выбранной компании
            selected_nomer_dogovora = request.POST.get('nomer_dogovora')  # Получаем номер договора

            if selected_nomer_dogovora:
                # Проверяем, существует ли закупка с выбранным номером договора
                try:
                    zakupki_instance = PredmetZakupki.objects.get(nomer_dogovora=selected_nomer_dogovora, company=selected_company)
                    # Получаем лоты, связанные с выбранным номером договора
                    lots_list = Lots.objects.filter(zakupki=zakupki_instance)
                except PredmetZakupki.DoesNotExist:
                    # Обработка случая, когда закупка не найдена
                    zakupki_instance = None
                    lots_list = []

    return render(request, 'filter.html', {
        'companies': companies,
        'selected_company': selected_company,
        'zakupki_list': zakupki_list,
        'selected_nomer_dogovora': selected_nomer_dogovora,
        'lots_list': lots_list,
    })

def calculate_price(request):
    if request.method == 'POST':
        total_price = request.POST.get('total_price', 0.00)
        return JsonResponse({'total_price': total_price})
    
@login_required
def table(request):
    companies = Company.objects.prefetch_related(
        'predmetzakupki_set__lots_set'
    ).all()
    context = {
        'companies': companies,
    }
    return render(request, 'table.html', context)

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
        'predmetzakupki_set__lots_set'
    ).all()
    
    for company_index, company in enumerate(companies, start=1):
        for zakupka in company.predmetzakupki_set.all():
            for lot in zakupka.lots_set.all():
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

def generate_pdf(request, zakupki_id):
    # Получаем информацию о закупке
    zakupka = get_object_or_404(PredmetZakupki, id=zakupki_id)
    company = zakupka.company
    lots = Lots.objects.filter(zakupki=zakupka)

    # Создаем HttpResponse с типом 'application/pdf'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="zakupka_{zakupki_id}.pdf"'


    # Создаем PDF с помощью ReportLab
    p = canvas.Canvas(response)
     # Подключаем шрифт
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'regforma/fonts/DejaVuSans.ttf'))
    p.setFont("DejaVuSans", 14)
    p.drawString(100, 800, f"Информация о закупке №{zakupka.nomer_dogovora}")
    p.setFont("DejaVuSans", 14)
    p.drawString(100, 770, f"Закупку провел: {request.user.last_name} {request.user.first_name}")
    p.drawString(100, 750, f"Дата регистрации в БД: {zakupka.data_creator_zakupki.strftime('%d.%m.%Y')}")
    # Добавьте остальную информацию здесь...

    # Закрываем PDF и возвращаем ответ
    p.showPage()
    p.save()
    return response