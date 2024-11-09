from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import datetime
from django_countries.fields import CountryField

class Company(models.Model):

    name = models.CharField(max_length=200, verbose_name='Название организации')
    adress = models.CharField(max_length=200, verbose_name='Юридический адрес')
    unp = models.CharField(max_length=200, verbose_name='УНП')
    author = models.ForeignKey(User, on_delete=models.CASCADE, default='1') # после внедрения в реальный проект убрать значение default='1'

class PredmetZakupki(models.Model):
    VID_ZAKUPKI_CHOICES = [
        ('Сравнительная таблица', 'Сравнительная таблица'),
        ('Прямая процедура', 'Прямая процедура'),
        ('Переход на прямую процедуру закупки', 'Переход на прямую процедуру закупки'),
        ('Упращенная процедура закупки до 15 БВ', 'Упращенная процедура закупки до 15 БВ'),
        ('Конкурентный лист', 'Конкурентный лист'),
        ('Открытый конкурс', 'Открытый конкурс'),
    ]
    
    vid_zakupki = models.CharField(
        max_length=200,
        choices=VID_ZAKUPKI_CHOICES,
        #default='Сравнительная таблица',  # Устанавливаем значение по умолчанию
        verbose_name='Вид процедуры закупки'
    )

    #vid_zakupki = models.CharField(max_length=200, verbose_name='Вид процедуры закупки')
    nomer_dogovora = models.CharField(max_length=200, verbose_name='Номер договора')
    data_dogovora = models.DateField(verbose_name='Дата заключения договора') #blank: Если установлено в True, поле может быть оставлено пустым в формах
    price_full = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость договора')  # Новое поле для цены
    data_creator_zakupki = models.DateField(default=timezone.now)  # Устанавливает текущую дату
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
                                
class Lots(models.Model):
    COUNTRY_CHOICES = [
    ('RU', 'Россия'),
    ('BY', 'Беларусь'),
    ('US', 'США'),
    ('CN', 'Китай'),
    # Добавьте другие страны по мере необходимости
]
    UNITS_CHOICES = [
    ('шт', 'штук'),
    ('m³', 'кубический метр (м³)'),
    ('л', 'литр (л)'),
    ('мл', 'миллилитр (мл)'),
    ('см³', 'кубический сантиметр (см³)'),
    ('баррель', 'баррель'),
    ('галлон', 'галлон'),
    ('м', 'метр (м)'),
    ('см', 'сантиметр (см)'),
    ('мм', 'миллиметр (мм)'),
    ('км', 'километр (км)'),
    ('дюйм', 'дюйм (in)'),
    ('фут', 'фут (ft)'),
    ('ярд', 'ярд (yd)'),
    ('мкм', 'микрометр (мкм)'),
    ('м²', 'квадратный метр (м²)'),
    ('см²', 'квадратный сантиметр (см²)'),
    ('га', 'гектар (га)'),
    ('акр', 'акр'),
    ('км²', 'квадратный километр (км²)'),
    ('кг', 'килограмм (кг)'),
    ('г', 'грамм (г)'),
    ('мг', 'миллиграмм (мг)'),
    ('т', 'тонна (т)'),
    ('ц', 'центнер (ц)'),
    ('унция', 'унция (oz)'),
    ('фунт', 'фунт (lb)'),
    ('Вт', 'ватт (Вт)'),
    ('кВт', 'киловатт (кВт)'),
    ('кВт·ч', 'киловатт-час (кВт·ч)'),
    ('моль/л', 'моль на литр (моль/л)'),
    ('г/л', 'грамм на литр (г/л)'),
    ('мг/л', 'миллиграмм на литр (мг/л)')
]
    number_lot = models.PositiveIntegerField(default=1, verbose_name='Номер лота')  # Поле для лота с положительным значением
    cod_okrb = models.CharField(max_length=200, verbose_name='Код ОКРБ')
    predmet_zakupki = models.CharField(max_length=200, verbose_name='Предмет закупки (что закупаем)')
    unit = models.IntegerField(verbose_name='Количество')
    ed_izmer = models.CharField(max_length=20, choices=UNITS_CHOICES, verbose_name='Единица измерения')
    country = models.CharField(max_length=200, choices=COUNTRY_CHOICES, verbose_name='Страна')
    price_lot = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Стоимость лота (БезНДС), руб.')
    zakupki = models.ForeignKey(PredmetZakupki, on_delete=models.CASCADE)

