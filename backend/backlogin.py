from getpass import getpass

class Usuario:
    def __init__(self, dni, contraseña):
        self.dni = dni
        self.contraseña = contraseña

    def verificar_credenciales(self, dni, contraseña):
        return self.dni == dni and self.contraseña == contraseña
    
class Sesion:
    def __init__ (self, usuario):
         self.usuario = usuario
         self.active = False
    def iniciar_sesion (self, verificacion_dni , verificacion_contraseña):
        if self.usuario.verificar_credenciales(verificacion_dni, verificacion_contraseña):
           self.active = True 
           print (f"inicio de sesion correcto para DNI {self.usuario.dni}")
        else:
            print (f"usuario o contraseña incorrectos ingrese de nuevo")

    def Cierre_sesion (self):
        if  self.active:
             self.active = False 
             print (f"sesion cerrada con exito")
        else:
            print (f"no hay sesion activa para cerrar ")  

if __name__ == "__main__":
    usuario = Usuario("12345678", "1234")   
    sesion = Sesion(usuario)

    while True:
        print("\n--- MENÚ ---")
        print("1. Iniciar sesión")
        print("2. Cerrar sesión")
        print("3. Salir")
        opcion = input("Elegí una opción: ")

        if opcion == "1":
            dni = input("DNI: ")
            contraseña = getpass ("Contraseña: ")   
            sesion.iniciar_sesion(dni, contraseña)
        elif opcion == "2":
            sesion.cerrar_sesion()
        elif opcion == "3":
            print("Hasta luego")
            break
        else:
            print("Opción inválida")

