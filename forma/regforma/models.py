from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django_countries.fields import CountryField


class Company(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название организации')
    adress = models.CharField(max_length=200, verbose_name='Юридический адрес')
    unp = models.CharField(max_length=200, verbose_name='УНП')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='companies')

    def __str__(self):
        return self.name


class PredmetZakupki(models.Model):
    VID_ZAKUPKI_CHOICES = [
        ('Сравнительная таблица', 'Сравнительная таблица'),
        ('Прямая процедура', 'Прямая процедура'),
        ('Переход на прямую процедуру закупки', 'Переход на прямую процедуру закупки'),
        ('Упрощенная процедура закупки до 15 БВ', 'Упрощенная процедура закупки до 15 БВ'),
        ('Конкурентный лист', 'Конкурентный лист'),
        ('Открытый конкурс', 'Открытый конкурс'),
    ]

    vid_zakupki = models.CharField(
        max_length=200,
        choices=VID_ZAKUPKI_CHOICES,
        verbose_name='Вид процедуры закупки'
    )
    nomer_dogovora = models.CharField(max_length=200, verbose_name='Номер договора')
    data_dogovora = models.DateField(verbose_name='Дата заключения договора')
    price_full = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость договора')
    data_creator_zakupki = models.DateField(default=timezone.now)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='zakupki')

    def __str__(self):
        return f"{self.vid_zakupki} - {self.nomer_dogovora}"


class Lots(models.Model):
    COUNTRY_CHOICES = [
        ('RU', 'Россия'),
        ('BY', 'Беларусь'),
        ('US', 'США'),
        ('CN', 'Китай'),
    ]

    UNITS_CHOICES = [
        ('шт', 'штук'),
        ('м³', 'кубический метр (м³)'),
        ('л', 'литр (л)'),
        # Остальные варианты...
    ]

    number_lot = models.PositiveIntegerField(default=1, verbose_name='Номер лота')
    cod_okrb = models.CharField(max_length=200, verbose_name='Код ОКРБ')
    predmet_zakupki = models.CharField(max_length=200, verbose_name='Предмет закупки (что закупаем)')
    unit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Количество')  # Для дробных значений
    ed_izmer = models.CharField(max_length=20, choices=UNITS_CHOICES, verbose_name='Единица измерения')
    country = models.CharField(max_length=200, choices=COUNTRY_CHOICES, verbose_name='Страна')
    price_lot = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Стоимость лота (БезНДС), руб.')
    zakupki = models.ForeignKey(PredmetZakupki, on_delete=models.CASCADE, related_name='lots')

    def __str__(self):
        return f"Лот {self.number_lot} - {self.predmet_zakupki}"
