from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def lista_documentos(request):
    return render(request, 'documentos/lista.html')
