from django.urls import path

from . import views

app_name = "biblioteca"

urlpatterns = [
    path("", views.listar_libros, name="listar_libros"),
    path("libros/nuevo/", views.registrar_libro, name="registrar_libro"),
    path("alumnos/", views.listar_alumnos, name="listar_alumnos"),
    path("alumnos/nuevo/", views.registrar_alumno, name="registrar_alumno"),
    path("prestamos/", views.listar_prestamos, name="listar_prestamos"),
    path("prestamos/nuevo/", views.registrar_prestamo, name="registrar_prestamo"),
    path("prestamos/<int:prestamo_id>/devolver/", views.registrar_devolucion, name="registrar_devolucion"),
]
