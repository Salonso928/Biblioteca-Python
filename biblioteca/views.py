from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import AlumnoForm, LibroForm, PrestamoForm
from .models import Alumno, Libro, Prestamo


def listar_libros(request):
    consulta = request.GET.get("q", "").strip()
    libros = Libro.objects.select_related("categoria").all()

    if consulta:
        libros = libros.filter(
            Q(nombre__icontains=consulta)
            | Q(autor__icontains=consulta)
            | Q(codigo__icontains=consulta)
        )

    return render(request, "biblioteca/libros/lista.html", {
        "libros": libros,
        "consulta": consulta,
    })


def listar_alumnos(request):
    alumnos = Alumno.objects.all()
    return render(request, "biblioteca/alumnos/lista.html", {
        "alumnos": alumnos,
    })


def registrar_libro(request):
    if request.method == "POST":
        form = LibroForm(request.POST)

        if form.is_valid():
            libro = form.save(commit=False)
            libro.stock_disponible = libro.stock_total
            libro.save()
            messages.success(request, "El libro se registró correctamente.")
            return redirect("biblioteca:listar_libros")
    else:
        form = LibroForm()

    return render(request, "biblioteca/libros/formulario.html", {
        "form": form,
    })


def registrar_alumno(request):
    if request.method == "POST":
        form = AlumnoForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "El alumno se registró correctamente.")
            return redirect("biblioteca:listar_alumnos")
    else:
        form = AlumnoForm()

    return render(request, "biblioteca/alumnos/formulario.html", {
        "form": form,
    })


def listar_prestamos(request):
    prestamos = Prestamo.objects.select_related("alumno", "libro").all()
    return render(request, "biblioteca/prestamos/lista.html", {
        "prestamos": prestamos,
    })


def registrar_prestamo(request):
    if request.method == "POST":
        form = PrestamoForm(request.POST)

        if "buscar" in request.POST:
            return render(request, "biblioteca/prestamos/formulario.html", {
                "form": form,
            })

        if form.is_valid():
            alumno = form.cleaned_data["alumno"]
            libro = form.cleaned_data["libro"]

            if alumno.estado == Alumno.Estado.SUSPENDIDO:
                messages.error(request, "El alumno está suspendido y no puede solicitar préstamos.")
            elif libro.stock_disponible <= 0:
                messages.error(request, "No hay ejemplares disponibles de este libro.")
            else:
                tiene_prestamo_atrasado = Prestamo.objects.filter(
                    alumno=alumno,
                    estado=Prestamo.Estado.ATRASADO,
                    fecha_devolucion_real__isnull=True,
                ).exists()

                if tiene_prestamo_atrasado:
                    messages.error(request, "El alumno tiene préstamos atrasados pendientes.")
                else:
                    with transaction.atomic():
                        libro = Libro.objects.select_for_update().get(pk=libro.pk)

                        if libro.stock_disponible <= 0:
                            messages.error(request, "No hay ejemplares disponibles de este libro.")
                        else:
                            prestamo = form.save(commit=False)
                            prestamo.estado = Prestamo.Estado.ACTIVO
                            prestamo.save()

                            libro.stock_disponible -= 1
                            libro.save(update_fields=("stock_disponible",))

                            messages.success(request, "Préstamo registrado correctamente.")
                            return redirect("biblioteca:listar_prestamos")
    else:
        form = PrestamoForm()

    return render(request, "biblioteca/prestamos/formulario.html", {
        "form": form,
    })


def registrar_devolucion(request, prestamo_id):
    try:
        prestamo = Prestamo.objects.select_related("libro").get(pk=prestamo_id)
    except Prestamo.DoesNotExist:
        raise Http404("Préstamo no encontrado")

    if request.method == "POST":
        if prestamo.estado == Prestamo.Estado.DEVUELTO:
            messages.warning(request, "Este préstamo ya fue devuelto.")
            return redirect("biblioteca:listar_prestamos")

        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().get(pk=prestamo.pk)
            libro = Libro.objects.select_for_update().get(pk=prestamo.libro_id)

            prestamo.fecha_devolucion_real = timezone.now()
            prestamo.estado = Prestamo.Estado.DEVUELTO
            prestamo.save(update_fields=(
                "fecha_devolucion_real",
                "estado",
            ))

            libro.stock_disponible += 1

            if libro.stock_disponible > libro.stock_total:
                libro.stock_disponible = libro.stock_total

            libro.save(update_fields=("stock_disponible",))

        messages.success(request, "Devolución registrada correctamente.")
        return redirect("biblioteca:listar_prestamos")

    return render(request, "biblioteca/prestamos/devolucion.html", {
        "prestamo": prestamo,
    })
