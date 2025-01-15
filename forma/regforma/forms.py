from django import forms
from .models import Company, PredmetZakupki, Lots

class ClassifikatorForm(forms.Form):
    code = forms.CharField(required=False, max_length=255)
    name = forms.CharField(required=False, max_length=255)

class CompanyForms(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'adress', 'unp']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'adress': forms.TextInput(attrs={'class': 'form-control'}),
            'unp': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ZakupkiForms(forms.ModelForm):
    class Meta:
        model = PredmetZakupki
        fields = ['vid_zakupki', 'nomer_dogovora', 'data_dogovora', 'price_full']
        widgets = {
            'vid_zakupki': forms.Select(attrs={'class': 'form-control'}),
            'nomer_dogovora': forms.TextInput(attrs={'class': 'form-control'}),
            'data_dogovora': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'style': 'width: 200px;',  # ширина поля для выбора даты
            }),
            'price_full': forms.NumberInput(attrs={
                'class': 'form-control',    
                'step': '0.01',
                'style': 'width: 200px;',  # ширина поля для ввода цены
            }),
        }

class LotsForms(forms.ModelForm):
    class Meta:
        model = Lots
        fields = ['number_lot', 'cod_okrb', 'predmet_zakupki', 'unit', 'ed_izmer', 'country', 'price_lot']
        widgets = {
            'number_lot': forms.NumberInput(attrs={'class': 'form-control'}),
            'cod_okrb': forms.TextInput(attrs={'class': 'form-control'}),
            'predmet_zakupki': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'ed_izmer': forms.Select(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'price_lot': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
        }
