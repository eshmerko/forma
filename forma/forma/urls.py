"""
URL configuration for forma project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.generic import RedirectView
from networkx import generate_gexf  # Импорт RedirectView
from regforma.views import (export_to_excel, filter_view, calculate_price, generate_pdf, menu, regforma, table, my_view, zakupki_detail)

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False)),  # перенаправление на логин
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('menu/', menu, name='menu'),
    path('admin/', admin.site.urls),
    path('regforma/', regforma, name='regforma'),
    path('filter/', filter_view, name='filter_view'),  # Новый маршрут для фильтрации
    path('calculate_price/', calculate_price, name='calculate_price'),
    path('my_view/', my_view, name='my_view'),
    path('table/', table, name='table'),
    path('table/export_excel/', export_to_excel, name='export_to_excel'),
    path('accounts/', include('django.contrib.auth.urls')),  # маршруты для логина и логаута
    path('zakupki/<int:zakupki_id>/', zakupki_detail, name='zakupki_detail'),
    path('zakupki/<int:zakupki_id>/generate_pdf/', generate_pdf, name='generate_pdf'),
]
