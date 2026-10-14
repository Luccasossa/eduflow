from django.shortcuts import render

def lista_archivos(request):
    return render(request, 'archivos/lista.html')