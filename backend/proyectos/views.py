from django.shortcuts import render

def lista_proyectos(request):
       return render(request, 'proyectos/lista.html')