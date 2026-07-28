import sys
import pandas as pd
import pdfplumber
import re
import tkinter as tk
from tkinter import filedialog

# Evitar UnicodeEncodeError con emojis en la consola de Windows (cp1252)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

def extraer_datos_pdf(ruta_pdf):
    aberturas_pdf = []
    
    patron = re.compile(
        r'Nombre:\s*(?P<codigo>\d+)\s+(?P<nom>[A-Za-z0-9]+)\s+(?P<orden>\d+)[\s\S]*?'
        r'Ancho:\s*(?P<ancho>\d+(?:\.\d+)?)[\s\S]*?'
        r'Alto:\s*(?P<alto>\d+(?:\.\d+)?)'
    )

    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            
            for match in patron.finditer(texto):
                aberturas_pdf.append({
                    'Codigo': match.group('codigo').strip(),
                    'Nomenclatura': match.group('nom').strip(),
                    'Orden': match.group('orden').strip(),
                    'Ancho_PDF': float(match.group('ancho')),
                    'Alto_PDF': float(match.group('alto'))
                })
                
    df_pdf = pd.DataFrame(aberturas_pdf)
    
    # --- NUEVA LÍNEA: Eliminar duplicados por salto de página en el PDF ---
    df_pdf.drop_duplicates(subset=['Codigo', 'Nomenclatura', 'Orden'], keep='first', inplace=True)
    
    return df_pdf

def auditar_fabricacion(ruta_pdf, ruta_bd, num_fabricacion):
    print(f"\n--- Iniciando auditoría para Fabricación N° {num_fabricacion} ---")
    
    # 1. Extraer datos del PDF
    print("Leyendo PDF de armado...")
    df_pdf = extraer_datos_pdf(ruta_pdf)
    if df_pdf.empty:
        print("❌ No se encontraron aberturas en el PDF. Revisa el formato.")
        return
    
    print(f"✅ Se leyeron {len(df_pdf)} aberturas del PDF de armado.")

    # 2. Descargar y leer la base de datos directo desde Google Sheets
    print("Conectando con Google Sheets y descargando datos en vivo...")
    try:
        df_bd = pd.read_csv(ruta_bd, skiprows=1, dtype=str) 
    except Exception as e:
        print(f"❌ Ocurrió un error al intentar leer el enlace de Google Sheets:\n{e}")
        return

# 3. Mapear las columnas exactas (Índices corregidos)
    idx_codigo = 2   # Columna 2 (Codigo de obra)
    idx_nom = 7      # Columna 7 (Nomenclatura planilla)
    idx_orden = 8    # Columna 8 (Numero de orden)
    idx_ancho = 15   # Columna 15 (Ancho)
    idx_alto = 16    # Columna 16 (Alto)
    idx_fabric = 34  # Columna 34 / AI 
    
    # Extraer usando .iloc SOLO las 6 columnas que necesitamos
    df_bd = df_bd.iloc[:, [idx_codigo, idx_nom, idx_orden, idx_ancho, idx_alto, idx_fabric]].copy()
    
    # Asignar nombres definitivos para trabajar
    df_bd.columns = ['Codigo', 'Nomenclatura', 'Orden', 'Ancho_BD', 'Alto_BD', 'Nro_Fabricacion']

    # 4. Filtrar la BD por el número de fabricación
    df_bd['Nro_Fabricacion'] = df_bd['Nro_Fabricacion'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    num_fabricacion_limpio = str(num_fabricacion).strip()
    
    df_filtrada = df_bd[df_bd['Nro_Fabricacion'] == num_fabricacion_limpio].copy()

    if df_filtrada.empty:
        print(f"⚠️ No se encontraron registros para la fabricación '{num_fabricacion_limpio}'.")
        return
        
    print(f"✅ Se encontraron {len(df_filtrada)} aberturas en la BD para esta fabricación.")

    # --- NUEVA LIMPIEZA PROFUNDA DE CLAVES PARA EL CRUCE ---
    
    # 1. Limpiar los datos provenientes de Sheets
    for col in ['Codigo', 'Nomenclatura', 'Orden']:
        df_filtrada[col] = df_filtrada[col].astype(str).str.strip()
        # Borrar decimales si Pandas los agregó (ej: '12.0' -> '12')
        df_filtrada[col] = df_filtrada[col].str.replace(r'\.0$', '', regex=True)
    
    # Asegurar que la nomenclatura esté en mayúsculas (ej: 'pv1' pasa a 'PV1')
    df_filtrada['Nomenclatura'] = df_filtrada['Nomenclatura'].str.upper()

    # 2. Limpiar los datos provenientes del PDF
    df_pdf['Codigo'] = df_pdf['Codigo'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    df_pdf['Orden'] = df_pdf['Orden'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    df_pdf['Nomenclatura'] = df_pdf['Nomenclatura'].astype(str).str.strip().str.upper()

    # Convertimos ancho y alto a números para poder hacer la comparación matemática
    df_filtrada['Ancho_BD'] = pd.to_numeric(df_filtrada['Ancho_BD'], errors='coerce')
    df_filtrada['Alto_BD'] = pd.to_numeric(df_filtrada['Alto_BD'], errors='coerce')
    
    # 5. Cruzar los datos 
    cruce = pd.merge(df_pdf, df_filtrada, on=['Codigo', 'Nomenclatura', 'Orden'], how='left')

    # 6. Chequear discrepancias
    errores = []
    for _, row in cruce.iterrows():
        abertura = f"{row['Codigo']} {row['Nomenclatura']} {row['Orden']}"
        
        if pd.isna(row['Ancho_BD']):
            errores.append(f"⚠️ {abertura}: Está en el PDF pero NO se encontró en la BD bajo la fabricación {num_fabricacion}.")
            continue
            
        if row['Ancho_PDF'] != row['Ancho_BD']:
            errores.append(f"❌ {abertura} - Error en ANCHO: Armado PDF={row['Ancho_PDF']} vs Sheets={row['Ancho_BD']}")
            
        if row['Alto_PDF'] != row['Alto_BD']:
            errores.append(f"❌ {abertura} - Error en ALTO: Armado PDF={row['Alto_PDF']} vs Sheets={row['Alto_BD']}")

    # 7. Imprimir Reporte
    print("\n" + "="*40)
    print("        RESULTADO DE LA AUDITORÍA")
    print("="*40)
    if not errores:
        print("🟢 ¡Todo perfecto! Las medidas del PDF coinciden exactamente con la Base de Datos.")
    else:
        print(f"🔴 Se encontraron {len(errores)} problemas:\n")
        for e in errores:
            print(e)


# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":

    # Iniciar ventana oculta de Tkinter
    root = tk.Tk()
    root.withdraw()
    
    print("Por favor, selecciona el PDF de la planilla de armado en la ventana que se abrió...")
    # Asegúrate de mirar si la ventana se abrió detrás de otra aplicación
    archivo_pdf = filedialog.askopenfilename(
        title="Seleccionar Planilla de Armado (PDF)",
        filetypes=[("Archivos PDF", "*.pdf")]
    )
    
    if not archivo_pdf:
        print("No seleccionaste ningún PDF. Cancelando ejecución...")
        exit()
        
    numero_fabricacion = input("\nIngresa el número de fabricación a auditar (ej. 61) y presiona Enter: ")
    
    # Ejecutamos pasando la ruta local del PDF y la URL de internet para el CSV
    auditar_fabricacion(archivo_pdf, "https://docs.google.com/spreadsheets/d/e/2PACX-1vRqXV6pwWMgPfMf-WwV9HLUdJx0tHBIJOFhuvUQ1FQPFK_Lvcuse9SAdvWT35yT-tvTMt0Pnun7xZYr/pub?gid=1177155904&single=true&output=csv", numero_fabricacion)