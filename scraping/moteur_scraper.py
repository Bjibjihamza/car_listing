
import os
import re
import requests
import unicodedata
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# Configuration des répertoires
DATA_DIR = "../data/moteur"
IMAGES_DIR = os.path.join(DATA_DIR, "images")

# Créer les répertoires s'ils n'existent pas
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Configuration de Selenium
options = Options()
options.add_argument("--headless")  # Exécuter en arrière-plan
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")  # Contourner la détection des bots

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# URL de base sans numéro de page
BASE_URL = "https://www.moteur.ma/fr/voiture/achat-voiture-occasion/"

# Initialiser le driver une seule fois
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def extract_id_from_url(url):
    """Extrait l'ID de l'annonce depuis l'URL."""
    match = re.search(r"/detail-annonce/(\d+)/", url)
    return match.group(1) if match else "N/A"

def sanitize_filename(filename):
    """Nettoie un nom de fichier pour qu'il soit valide sur le système d'exploitation."""
    # Remplacer les caractères non-alphanumériques par des underscores
    filename = re.sub(r'[^\w\s-]', '_', filename)
    # Normaliser les caractères accentués
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    # Remplacer les espaces par des underscores
    filename = re.sub(r'\s+', '_', filename)
    return filename

def download_image(url, folder_path, index):
    """Télécharge une image à partir d'une URL avec des en-têtes améliorés."""
    try:
        print(f"Téléchargement de {url} vers {folder_path}")
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            file_extension = url.split('.')[-1]
            if '?' in file_extension:
                file_extension = file_extension.split('?')[0]
            if not file_extension or len(file_extension) > 5:
                file_extension = "jpg"  # Extension par défaut si problème
            image_path = os.path.join(folder_path, f"image_{index}.{file_extension}")
            with open(image_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Image enregistrée : {image_path}")
            return True
        else:
            print(f"❌ Erreur HTTP {response.status_code} pour {url}")
        return False
    except Exception as e:
        print(f"⚠️ Erreur lors du téléchargement de l'image {url}: {e}")
        return False

def scrape_page(page_url):
    """Scrape les annonces d'une page donnée."""
    driver.get(page_url)
    
    # Attendre que les annonces chargent (timeout de 10 sec)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "row-item"))
        )
    except:
        print(f"Aucune annonce trouvée sur {page_url}")
        return []
    
    # Récupérer les annonces
    car_elements = driver.find_elements(By.CLASS_NAME, "row-item")
    data = []
    
    for car in car_elements:
        try:
            # Titre
            title_element = car.find_element(By.CLASS_NAME, "title_mark_model")
            title = title_element.text.strip() if title_element else "N/A"
            
            # Lien de l'annonce et extraction de l'ID
            try:
                link_element = car.find_element(By.XPATH, ".//h3[@class='title_mark_model']/a")
                link = link_element.get_attribute("href") if link_element else "N/A"
                ad_id = extract_id_from_url(link)  # Extraire l'ID
            except:
                link, ad_id = "N/A", "N/A"
            
            # Prix
            try:
                price_element = car.find_element(By.CLASS_NAME, "PriceListing")
                price = price_element.text.strip()
            except:
                price = "N/A"
            
            # Année, Ville, Carburant (On vérifie la présence)
            meta_elements = car.find_elements(By.TAG_NAME, "li")
            year = meta_elements[1].text.strip() if len(meta_elements) > 1 else "N/A"
            city = meta_elements[2].text.strip() if len(meta_elements) > 2 else "N/A"
            fuel = meta_elements[3].text.strip() if len(meta_elements) > 3 else "N/A"
            
            # Ajouter les données
            data.append({
                "ID": ad_id,
                "Titre": title,
                "Prix": price,
                "Année": year,
                "Ville": city,
                "Carburant": fuel,
                "Lien": link
            })
        
        except Exception as e:
            print(f"Erreur sur une annonce : {e}")
    
    return data

def scrape_multiple_pages(max_pages=1):
    """Scrape plusieurs pages du site en respectant le format de pagination (0, 30, 60, 90)"""
    all_data = []
    
    for page_offset in range(0, max_pages * 30, 30):
        print(f"Scraping page avec offset {page_offset}...")
        page_url = f"{BASE_URL}{page_offset}" if page_offset > 0 else BASE_URL
        all_data.extend(scrape_page(page_url))
        time.sleep(3)  # Pause pour éviter le blocage
    
    return all_data

def scrape_detail_page(url, ad_id, title):
    """Scrape les détails d'une annonce spécifique."""
    try:
        # Accéder à la page de détail
        driver.get(url)
        time.sleep(3)  # Attendre le chargement de la page
        
        # Créer un dossier pour les images de cette annonce
        folder_name = f"{ad_id}_{sanitize_filename(title)}"
        folder_path = os.path.join(IMAGES_DIR, folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"📂 Dossier créé : {folder_path}")
        
        # Récupérer les détails du véhicule
        details = {}
        
        # 1. Prix
        try:
            price_element = driver.find_element(By.CSS_SELECTOR, "h1 span")
            details["Prix"] = price_element.text.strip()
        except Exception as e:
            print(f"Erreur extraction prix: {e}")
            details["Prix"] = "N/A"
        
        # 2. Informations techniques dans les detail_line
        detail_lines = driver.find_elements(By.CLASS_NAME, "detail_line")
        
        for line in detail_lines:
            try:
                spans = line.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    key = spans[0].text.strip()
                    value = spans[1].text.strip()
                    
                    if "Kilométrage" in key:
                        details["Kilométrage"] = value
                    elif "Année" in key:
                        details["Année"] = value
                    elif "Boite de vitesses" in key:
                        details["Transmission"] = value
                    elif "Carburant" in key:
                        details["Type de carburant"] = value
                    elif "Date" in key:
                        details["Date de publication"] = value
                    elif "Puissance" in key:
                        details["Puissance fiscale"] = value
                    elif "Nombre de portes" in key:
                        details["Nombre de portes"] = value
                    elif "Première main" in key:
                        details["Première main"] = value
                    elif "Véhicule dédouané" in key:
                        details["Dédouané"] = value
            except Exception as e:
                print(f"Erreur lors de l'extraction d'une ligne de détail: {e}")
        
        # 3. Description
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, "div.options div.col-md-12")
            details["Description"] = description_element.text.strip()
        except Exception as e:
            print(f"Erreur extraction description: {e}")
            details["Description"] = "N/A"
        
        # 4. Nom du vendeur
        try:
            seller_element = driver.find_element(By.CSS_SELECTOR, "a[href*='stock-professionnel']")
            details["Créateur"] = seller_element.text.strip()
        except Exception as e:
            print(f"Erreur extraction vendeur: {e}")
            details["Créateur"] = "N/A"
        
        # 5. Ville
        try:
            city_element = driver.find_element(By.CSS_SELECTOR, "a[href*='ville']")
            details["Ville"] = city_element.text.strip()
        except Exception as e:
            print(f"Erreur extraction ville: {e}")
            details["Ville"] = "N/A"
        
        # 6. Images - Méthode améliorée de téléchargement
        image_count = 0
        try:
            # Trouver les éléments d'image
            image_elements = driver.find_elements(By.CSS_SELECTOR, "img[data-u='image']")
            
            if not image_elements:
                print("⚠️ Aucune image trouvée sur la page. Essai d'une sélection alternative...")
                # Essayer une autre méthode de sélection
                image_elements = driver.find_elements(By.CSS_SELECTOR, ".swiper-slide img")
                
            print(f"Trouvé {len(image_elements)} images potentielles")
            
            for index, img in enumerate(image_elements):
                img_url = img.get_attribute("src")
                if img_url and "http" in img_url:
                    success = download_image(img_url, folder_path, index + 1)
                    if success:
                        image_count += 1
                else:
                    print(f"URL d'image invalide: {img_url}")
            
            # Si toujours pas d'images, essayer de chercher dans le code source
            if image_count == 0:
                print("Recherche d'images dans le code source...")
                page_source = driver.page_source
                img_urls = re.findall(r'src=[\'"]([^\'"]*\.(?:jpg|jpeg|png|gif)(?:\?[^\'"]*)?)[\'"]', page_source)
                for index, img_url in enumerate(set(img_urls)):
                    if "http" in img_url and "thumb" not in img_url.lower():
                        success = download_image(img_url, folder_path, index + 1)
                        if success:
                            image_count += 1
            
            print(f"📸 {image_count} images téléchargées pour {title}")
        except Exception as e:
            print(f"Erreur lors de l'extraction des images: {e}")
        
        # Ajouter le nombre d'images téléchargées
        details["Nombre d'images"] = str(image_count)
        
        # Ajouter l'ID, le titre, l'URL et le dossier d'images
        details["ID"] = ad_id
        details["Titre"] = title
        details["URL de l'annonce"] = url
        details["Dossier d'images"] = folder_name
        
        return details
        
    except Exception as e:
        print(f"❌ Erreur lors du scraping de la page {url}: {e}")
        return {
            "ID": ad_id,
            "Titre": title,
            "URL de l'annonce": url,
            "Erreur": str(e)
        }

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(DATA_DIR, f"moteur_ma_data_{timestamp}.csv")
    
    try:
        # Étape 1: Récupérer les annonces des pages de liste
        print("🔍 Démarrage du scraping des pages de liste...")
        car_listings = scrape_multiple_pages(max_pages=1)  # 4 pages (0, 30, 60, 90)
        print(f"✅ Scraping des listes terminé ! {len(car_listings)} annonces trouvées.")
        
        # Sauvegarde intermédiaire (optionnelle)
        listings_df = pd.DataFrame(car_listings)
        temp_csv_path = os.path.join(DATA_DIR, "temp_listings.csv")
        listings_df.to_csv(temp_csv_path, index=False, encoding="utf-8-sig")
        print(f"💾 Sauvegarde intermédiaire des listings dans {temp_csv_path}")
        
        # Étape 2: Extraire les détails pour chaque annonce
        print("\n🔎 Démarrage de l'extraction des détails pour chaque annonce...")
        detailed_data = []
        
        for index, listing in enumerate(car_listings):
            try:
                ad_id = listing["ID"]
                title = listing["Titre"]
                link = listing["Lien"]
                
                print(f"[{index+1}/{len(car_listings)}] Scraping de l'annonce: {title}")
                
                if link and link != "N/A" and "http" in link:
                    # Extraire les détails de la page
                    details = scrape_detail_page(link, ad_id, title)
                    detailed_data.append(details)
                    
                    # Pause pour éviter le blocage
                    time.sleep(2 + (index % 3))  # Pause variable entre 2 et 4 secondes
                else:
                    print(f"❌ Lien invalide pour l'annonce {ad_id}: {link}")
                    detailed_data.append({
                        "ID": ad_id,
                        "Titre": title,
                        "URL de l'annonce": link,
                        "Erreur": "Lien invalide"
                    })
            except Exception as e:
                print(f"❌ Erreur lors du traitement de l'annonce {index}: {e}")
        
        # Étape 3: Convertir en DataFrame et enregistrer
        print("\n💾 Préparation et sauvegarde des données complètes...")
        result_df = pd.DataFrame(detailed_data)
        
        # Réorganiser les colonnes
        columns_order = [
            "ID", "Titre", "Prix", "Date de publication", "Année", 
            "Type de carburant", "Transmission", "Kilométrage", 
            "Puissance fiscale", "Nombre de portes", "Première main", 
            "Dédouané", "Description", "Ville", "Créateur", 
            "URL de l'annonce", "Dossier d'images", "Nombre d'images"
        ]
        
        # Filtrer pour inclure seulement les colonnes présentes
        actual_columns = [col for col in columns_order if col in result_df.columns]
        result_df = result_df[actual_columns]
        
        # Enregistrer les données
        result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"✅ Scraping complet terminé ! {len(result_df)} annonces traitées.")
        print(f"📊 Données enregistrées dans {output_file}")
        
        # Supprimer le fichier temporaire
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        
        # Afficher des statistiques
        successful_images = sum(int(row.get("Nombre d'images", 0)) for _, row in result_df.iterrows())
        print(f"📊 Statistiques:")
        print(f"  - Annonces traitées: {len(result_df)}")
        print(f"  - Images téléchargées: {successful_images}")
        print(f"  - Moyenne d'images par annonce: {successful_images/len(result_df) if len(result_df) > 0 else 0:.1f}")
        
    except Exception as e:
        print(f"❌ Erreur globale: {e}")
    finally:
        # Fermer le navigateur
        driver.quit()
        print("🏁 Programme terminé.")

if __name__ == "__main__":
    main()