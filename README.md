# 📚 Sistema de Biblioteca Universitaria

Proyecto web desarrollado en **Python (Django)** conectado a **SQL Server** con **Pandas**, **NumPy** y **Bootstrap 5**.

---

## 🛠️ Requisitos Previos (Windows)

* **Python 3.10+** (con *"Add Python to PATH"* marcado).
* **SQL Server** y **ODBC Driver for SQL Server** (v17 o v18).
  * *¿No tienes el driver ODBC?* Busca **"Download ODBC Driver for SQL Server"** en Microsoft, instala la versión de 64 bits (`.msi`) y reinicia tu terminal. Puedes verificar el nombre exacto en Windows buscando **Orígenes de datos ODBC (64 bits) -> Controladores**.
* **Git**.

---

## 🚀 Instalación y Ejecución (Windows)

1. **Clonar el repositorio:**
   ```powershell
   git clone <URL_DEL_REPOSITORIO>
   cd LibreriaPython
   ```

2. **Crear y activar el entorno virtual:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   *(Si PowerShell bloquea el script, ejecuta `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` o usa CMD con `.venv\Scripts\activate.bat`).*
3. **Asignar el venv al proyecto de VSCode**

   Abre un archivo .py cualquiera en VSCODE

   Presiona ```Ctrl + Shift + P``` para abrir la paleta de comandos.

   Escribe y selecciona: ```Python: Select Interpreter.```

   Elige la opción que apunta a ```.\.venv\Scripts\python.exe``` creado del propio proyecto.

4. **Instalar dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Crear la base de datos vacía en SQL Server:**
   ```sql
   CREATE DATABASE BibliotecaDB;
   ```

6. **Configurar variables de entorno:**
   ```powershell
   copy .envEjemplo .env
   ```
   Copia y crea el archivo `.env` a partir del archivo `.envEjemplo` y ajusta el servidor, nombre de BD, usuario/contraseña y el nombre exacto de tu driver ODBC.

7. **Generar tablas y levantar el servidor:**
   ```powershell
   python manage.py migrate
   python manage.py runserver
   ```
   *(Opcional: `python manage.py createsuperuser` para entrar a `/admin/`).*

Abre en el navegador: **`http://127.0.0.1:8000/`**