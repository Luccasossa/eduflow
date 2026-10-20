from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def lista_archivos(request):
    return render(request, 'archivos/lista.html')
