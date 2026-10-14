from django.shortcuts import render

def lista_tareas(request):
    return render(request, 'tareas/lista.html')