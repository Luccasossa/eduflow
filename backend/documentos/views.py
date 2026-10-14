from django.shortcuts import render

def lista_documentos(request):
    return render(request, 'documentos/lista.html')