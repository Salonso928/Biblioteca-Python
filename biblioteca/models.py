from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self) -> str:
        return self.nombre


class Alumno(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        SUSPENDIDO = "Suspendido", "Suspendido"

    codigo_alumno = models.CharField(
        max_length=9,
        unique=True,
        validators=(
            RegexValidator(
                regex=r"^u[0-9]{8}$",
                message="El código debe tener el formato u seguido de 8 dígitos.",
            ),
        ),
    )
    nombre = models.CharField(max_length=150)
    carrera = models.CharField(max_length=150)
    correo = models.EmailField(max_length=254)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    class Meta:
        ordering = ("codigo_alumno",)
        verbose_name = "Alumno"
        verbose_name_plural = "Alumnos"

    def __str__(self) -> str:
        return f"{self.codigo_alumno} - {self.nombre}"


class Libro(models.Model):
    codigo = models.AutoField(primary_key=True)
    isbn = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=200, unique=True)
    autor = models.CharField(max_length=200)
    editorial = models.CharField(max_length=150)
    anio_publicacion = models.PositiveIntegerField()
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="libros",
    )
    stock_total = models.PositiveIntegerField()
    stock_disponible = models.PositiveIntegerField()

    class Meta:
        ordering = ("nombre",)
        verbose_name = "Libro"
        verbose_name_plural = "Libros"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(stock_disponible__lte=models.F("stock_total")),
                name="stock_disponible_menor_o_igual_stock_total",
            ),
        )

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nombre}"


class Prestamo(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        DEVUELTO = "Devuelto", "Devuelto"
        ATRASADO = "Atrasado", "Atrasado"

    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.PROTECT,
        related_name="prestamos",
    )
    libro = models.ForeignKey(
        Libro,
        on_delete=models.PROTECT,
        related_name="prestamos",
    )
    fecha_prestamo = models.DateTimeField(auto_now_add=True)
    fecha_devolucion_esperada = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
    )

    class Meta:
        ordering = ("-fecha_prestamo",)
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"

    def __str__(self) -> str:
        return f"{self.alumno.codigo_alumno} - {self.libro.codigo}"
