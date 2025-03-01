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
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

def scrape_detail_page(driver, url, ad_id, title, price_from_csv):
    """Scrape les détails d'une annonce spécifique, en utilisant le prix du CSV."""
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
        
        # 1. Prix - Utiliser la valeur du CSV au lieu de scraper
        details["Prix"] = price_from_csv
        
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
            seller_element = driver.find_element(By.XPATH, "//a[contains(@href, 'stock-professionnel') and .//i[contains(@class, 'icon-normal-megaphone')]]")
            details["Créateur"] = seller_element.text.strip() if seller_element.text.strip() else "N/A"
            
        except Exception as e:
            print(f"Erreur extraction vendeur: {e}")
            details["Créateur"] = "N/A"

        
        # 5. Ville
        try:
            city_element = driver.find_element(By.CSS_SELECTOR, "a[href*='ville']")
            details["Sector"] = city_element.text.strip()
        except Exception as e:
            print(f"Erreur extraction ville: {e}")
            details["Sector"] = "N/A"
        
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
            "Prix": price_from_csv,  # Inclure le prix du CSV même en cas d'erreur
            "Erreur": str(e)
        }

def load_listings_file():
    """Charge le fichier de listings le plus récent."""
    try:
        # Essayer d'abord de lire le pointeur vers le fichier le plus récent
        pointer_file = os.path.join(DATA_DIR, "latest_listings_file.txt")
        if os.path.exists(pointer_file):
            with open(pointer_file, 'r') as f:
                latest_file = f.read().strip()
                if os.path.exists(latest_file):
                    print(f"✅ Utilisation du fichier indiqué par le pointeur: {latest_file}")
                    return latest_file
                
        # Si pas de pointeur ou fichier inexistant, chercher le plus récent CSV
        csv_files = [f for f in os.listdir(DATA_DIR) if f.startswith("moteur_ma_listings") and f.endswith(".csv")]
        if not csv_files:
            raise FileNotFoundError("Aucun fichier de listings trouvé dans le répertoire.")
        
        # Prendre le fichier le plus récent
        latest_file = sorted(csv_files)[-1]
        latest_path = os.path.join(DATA_DIR, latest_file)
        print(f"✅ Fichier de listings le plus récent: {latest_path}")
        return latest_path
        
    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier de listings: {e}")
        return None

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(DATA_DIR, f"moteur_ma_details.csv")
    
    # Charger le fichier de listings
    listings_file = load_listings_file()
    if not listings_file:
        print("❌ Impossible de continuer sans fichier de listings.")
        return
    
    # Charger les données du CSV
    try:
        listings_df = pd.read_csv(listings_file, encoding="utf-8-sig")
        print(f"📊 {len(listings_df)} annonces chargées depuis {listings_file}")
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier CSV: {e}")
        return
    
    # Initialiser le driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Étape 1: Extraire les détails pour chaque annonce
        print("\n🔎 Démarrage de l'extraction des détails pour chaque annonce...")
        detailed_data = []
        
        for index, row in listings_df.iterrows():
            try:
                ad_id = row["ID"]
                title = row["Titre"]
                link = row["Lien"]
                price_from_csv = row.get("Prix", "N/A")  # Récupérer le prix du CSV
                
                print(f"[{index+1}/{len(listings_df)}] Scraping de l'annonce: {title} - Prix CSV: {price_from_csv}")
                
                if link and link != "N/A" and "http" in link:
                    # Extraire les détails de la page, en transmettant le prix du CSV
                    details = scrape_detail_page(driver, link, ad_id, title, price_from_csv)
                    detailed_data.append(details)
                    
                    # Pause pour éviter le blocage
                    time.sleep(2 + (index % 3))  # Pause variable entre 2 et 4 secondes
                else:
                    print(f"❌ Lien invalide pour l'annonce {ad_id}: {link}")
                    detailed_data.append({
                        "ID": ad_id,
                        "Titre": title,
                        "Prix": price_from_csv,  # Inclure le prix du CSV
                        "URL de l'annonce": link,
                        "Erreur": "Lien invalide"
                    })
            except Exception as e:
                print(f"❌ Erreur lors du traitement de l'annonce {index}: {e}")
        
        # Étape 2: Convertir en DataFrame et enregistrer
        print("\n💾 Préparation et sauvegarde des données complètes...")
        result_df = pd.DataFrame(detailed_data)
        
        # Réorganiser les colonnes
        columns_order = [
            "ID", "Titre", "Prix", "Date de publication", "Année", 
            "Type de carburant", "Transmission", "Kilométrage", 
            "Puissance fiscale", "Nombre de portes", "Première main", 
            "Dédouané", "Description", "Sector", "Créateur", 
            "URL de l'annonce", "Dossier d'images", "Nombre d'images"
        ]
        
        # Filtrer pour inclure seulement les colonnes présentes
        actual_columns = [col for col in columns_order if col in result_df.columns]
        result_df = result_df[actual_columns]
        
        # Enregistrer les données
        result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"✅ Scraping détaillé terminé ! {len(result_df)} annonces traitées.")
        print(f"📊 Données enregistrées dans {output_file}")
        
        # Afficher des statistiques
        successful_images = sum(int(row.get("Nombre d'images", "0")) for _, row in result_df.iterrows())
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