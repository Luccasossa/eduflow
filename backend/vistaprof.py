
import json
import os

ARCHIVO = "calificaciones.json"

# Cargar calificaciones guardadas
if os.path.exists(ARCHIVO):
    with open(ARCHIVO, "r", encoding="utf-8") as archivo:
        calificaciones = json.load(archivo)
else:
    calificaciones = []

# Ingresar datos
while True:
    print("\n--- EDUFLOW | Calificaciones del profesor ---")

    alumno = input("Nombre del alumno (o salir): ")

    if alumno.lower() == "salir":
        break

    materia = input("Materia: ")
    tarea = input("Nombre de la tarea: ")

    try:
        nota = float(input("Calificación (1 al 10): "))

        if nota < 1 or nota > 10:
            print("La nota debe estar entre 1 y 10.")
            continue

    except ValueError:
        print("Ingresá una nota numérica válida.")
        continue

    # Guardar calificación
    calificaciones.append({
        "alumno": alumno,
        "materia": materia,
        "tarea": tarea,
        "nota": nota
    })

    with open(ARCHIVO, "w", encoding="utf-8") as archivo:
        json.dump(calificaciones, archivo, indent=4, ensure_ascii=False)

    print("¡Calificación guardada correctamente!")

# Mostrar calificaciones guardadas
print("\n--- CALIFICACIONES REGISTRADAS ---")

for registro in calificaciones:
    print(
        f"Alumno: {registro['alumno']} | "
        f"Materia: {registro['materia']} | "
        f"Tarea: {registro['tarea']} | "
        f"Nota: {registro['nota']}"
    )

print("\nLos datos están guardados en", ARCHIVO)
 
