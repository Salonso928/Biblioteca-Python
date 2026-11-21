from django.contrib import admin

from .models import Alumno, Categoria, Libro, Prestamo


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_alumno",
        "nombre",
        "carrera",
        "correo",
        "estado",
    )
    list_filter = ("estado", "carrera")
    search_fields = (
        "codigo_alumno",
        "nombre",
        "correo",
    )


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "isbn",
        "nombre",
        "autor",
        "categoria",
        "stock_total",
        "stock_disponible",
    )
    list_filter = ("categoria",)
    search_fields = (
        "codigo",
        "isbn",
        "nombre",
        "autor",
        "editorial",
    )


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "alumno",
        "libro",
        "fecha_prestamo",
        "fecha_devolucion_esperada",
        "fecha_devolucion_real",
        "estado",
    )
    list_filter = ("estado",)
    search_fields = (
        "alumno__codigo_alumno",
        "alumno__nombre",
        "libro__codigo",
        "libro__nombre",
    )
