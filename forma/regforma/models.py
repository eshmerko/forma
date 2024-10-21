from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import datetime

class Company(models.Model):

    name = models.CharField(max_length=200, verbose_name='Название организации')
    adress = models.CharField(max_length=200, verbose_name='Юридический адрес')
    unp = models.CharField(max_length=200, verbose_name='УНП')
    author = models.ForeignKey(User, on_delete=models.CASCADE, default='1') # после внедрения в реальный проект убрать значение default='1'

class PredmetZakupki(models.Model):

    vid_zakupki = models.CharField(max_length=200, verbose_name='Вид процедуры закупки')
    nomer_dogovora = models.CharField(max_length=200, verbose_name='Номер договора')
    data_dogovora = models.DateField(verbose_name='Дата заключения договора') #blank: Если установлено в True, поле может быть оставлено пустым в формах
    price_full = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость договора')  # Новое поле для цены
    data_creator_zakupki = models.DateField(default=timezone.now)  # Устанавливает текущую дату
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
                                
class Lots(models.Model):

    number_lot = models.PositiveIntegerField(default=1, verbose_name='Номер лота')  # Поле для лота с положительным значением
    cod_okrb = models.CharField(max_length=200, verbose_name='Код ОКРБ')
    predmet_zakupki = models.CharField(max_length=200, verbose_name='Предмет закупки (что закупаем)')
    unit = models.IntegerField(verbose_name='Количество')
    ed_izmer = models.CharField(max_length=20, verbose_name='Единица измерения')
    country = models.CharField(max_length=200, verbose_name='Страна')
    price_lot = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Стоимость лота (БезНДС), руб.')
    zakupki = models.ForeignKey(PredmetZakupki, on_delete=models.CASCADE)

