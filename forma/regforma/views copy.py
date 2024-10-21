from django.shortcuts import render, redirect
from django.forms import modelformset_factory
from .forms import CompanyForms, ZakupkiForms, LotsForms
from .models import Company, Zakupki, Lots

def index(request):
    # Создаем formset для лотов
    LotsFormSet = modelformset_factory(Lots, form=LotsForms, extra=1)
    
    if request.method == 'POST':
        company_form = CompanyForms(request.POST)
        zakupki_form = ZakupkiForms(request.POST)
        formset = LotsFormSet(request.POST)
        
        if company_form.is_valid() and zakupki_form.is_valid() and formset.is_valid():
            # Сохранение или получение компании
            company = company_form.save(commit=False)
            company_instance, created = Company.objects.get_or_create(
                name=company.name,
                unp=company.unp,
                defaults={'adress': company.adress}
            )
            
            # Сохранение или получение закупки
            zakupki = zakupki_form.save(commit=False)
            zakupki.company = company_instance
            
            # Проверьте, что поле data_dogovora заполняется
            if not zakupki.data_dogovora:
                print("data_dogovora is empty")  # Это поможет вам отладить проблему
            
            zakupki_instance, created = Zakupki.objects.get_or_create(
                nomer_dogovora=zakupki.nomer_dogovora,
                company=company_instance,
                defaults={'data_dogovora': zakupki.data_dogovora, 'price_full': zakupki.price_full}
            )

            # Сохранение каждого лота из formset
            for form in formset:
                lot = form.save(commit=False)
                lot.zakupki = zakupki_instance
                lot.save()

            return redirect('index')
    
    else:
        company_form = CompanyForms()
        zakupki_form = ZakupkiForms()
        formset = LotsFormSet(queryset=Lots.objects.none())
    
    return render(request, 'index.html', {
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
            zakupki_list = Zakupki.objects.filter(company=selected_company)  # Получаем закупки для выбранной компании
            selected_nomer_dogovora = request.POST.get('nomer_dogovora')  # Получаем номер договора

            if selected_nomer_dogovora:
                # Проверяем, существует ли закупка с выбранным номером договора
                try:
                    zakupki_instance = Zakupki.objects.get(nomer_dogovora=selected_nomer_dogovora, company=selected_company)
                    # Получаем лоты, связанные с выбранным номером договора
                    lots_list = Lots.objects.filter(zakupki=zakupki_instance)
                except Zakupki.DoesNotExist:
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
