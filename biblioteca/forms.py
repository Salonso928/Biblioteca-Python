from django import forms
from django.db.models import Q

from .models import Alumno, Libro, Prestamo


class LibroForm(forms.ModelForm):
    class Meta:
        model = Libro
        fields = (
            "isbn",
            "nombre",
            "autor",
            "editorial",
            "anio_publicacion",
            "categoria",
            "stock_total",
        )
        widgets = {
            "anio_publicacion": forms.NumberInput(attrs={"min": 0}),
            "stock_total": forms.NumberInput(attrs={"min": 1}),
        }


class AlumnoForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = (
            "codigo_alumno",
            "nombre",
            "carrera",
            "correo",
            "estado",
        )
        widgets = {
            "codigo_alumno": forms.TextInput(
                attrs={
                    "pattern": "u[0-9]{8}",
                    "placeholder": "u23329291",
                    "maxlength": "9",
                }
            ),
        }


class PrestamoForm(forms.ModelForm):
    alumno_busqueda = forms.CharField(
        required=False,
        label="Buscar alumno",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Nombre o código del alumno",
                "class": "form-control mb-2",
            }
        ),
    )
    libro_busqueda = forms.CharField(
        required=False,
        label="Buscar libro",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Nombre, autor o código del libro",
                "class": "form-control mb-2",
            }
        ),
    )

    class Meta:
        model = Prestamo
        fields = (
            "alumno",
            "libro",
            "fecha_devolucion_esperada",
        )
        widgets = {
            "alumno": forms.Select(attrs={"class": "form-select mb-3"}),
            "libro": forms.Select(attrs={"class": "form-select mb-3"}),
            "fecha_devolucion_esperada": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        alumno_busqueda = ""
        libro_busqueda = ""

        if args:
            data = args[0]
        else:
            data = kwargs.get("data")

        if data:
            alumno_busqueda = data.get("alumno_busqueda", "").strip()
            libro_busqueda = data.get("libro_busqueda", "").strip()

        alumnos = Alumno.objects.all()
        libros = Libro.objects.all()

        if alumno_busqueda:
            alumnos = alumnos.filter(
                Q(nombre__icontains=alumno_busqueda)
                | Q(codigo_alumno__icontains=alumno_busqueda)
            )

        if libro_busqueda:
            libros = libros.filter(
                Q(nombre__icontains=libro_busqueda)
                | Q(codigo__icontains=libro_busqueda)
                | Q(autor__icontains=libro_busqueda)
            )

        self.fields["alumno"].queryset = alumnos
        self.fields["libro"].queryset = libros
