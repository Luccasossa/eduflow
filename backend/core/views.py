from django.shortcuts import render

# Create your views here.
def inicioalumno(request):
    return render(request, 'core/inicioalumno.html')


def inicioprofe(request):
    return render(request, 'core/inicioprofe.html')