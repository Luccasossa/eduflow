#from django.shortcuts import render
#from tareas.models import Tarea #nuevoc

#def lista_archivos(request):
#   return render(request, 'archivos/lista.html')


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Archivo, Carpeta


@login_required
def lista_archivos(request):
    archivos = Archivo.objects.filter(propietario=request.user)
    carpetas = Carpeta.objects.filter(propietario=request.user)

    contexto = {
        'archivos': archivos,
        'carpetas': carpetas,
    }

    return render(request, 'archivos/lista.html', contexto)


@login_required
def subir_archivo(request):
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']

        Archivo.objects.create(
            archivo=archivo,
            propietario=request.user
        )

        return redirect('lista_archivos')

    return redirect('lista_archivos')
