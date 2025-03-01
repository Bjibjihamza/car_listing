import os
import re
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

# Créer les répertoires s'ils n'existent pas
os.makedirs(DATA_DIR, exist_ok=True)

# Configuration de Selenium
options = Options()
options.add_argument("--headless")  # Exécuter en arrière-plan
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")  # Contourner la détection des bots

# URL de base sans numéro de page
BASE_URL = "https://www.moteur.ma/fr/voiture/achat-voiture-occasion/"

def extract_id_from_url(url):
    """Extrait l'ID de l'annonce depuis l'URL."""
    match = re.search(r"/detail-annonce/(\d+)/", url)
    return match.group(1) if match else "N/A"

def scrape_page(driver, page_url):
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

def scrape_multiple_pages(driver, max_pages=1):
    """Scrape plusieurs pages du site en respectant le format de pagination (0, 30, 60, 90)"""
    all_data = []
    
    for page_offset in range(0, max_pages * 30, 30):
        print(f"Scraping page avec offset {page_offset}...")
        page_url = f"{BASE_URL}{page_offset}" if page_offset > 0 else BASE_URL
        all_data.extend(scrape_page(driver, page_url))
        time.sleep(3)  # Pause pour éviter le blocage
    
    return all_data

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(DATA_DIR, f"moteur_ma_listings.csv")
    
    # Initialiser le driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Étape 1: Récupérer les annonces des pages de liste
        print("🔍 Démarrage du scraping des pages de liste...")
        car_listings = scrape_multiple_pages(driver, max_pages=1)  # Nombre de pages à scraper
        print(f"✅ Scraping des listes terminé ! {len(car_listings)} annonces trouvées.")
        
        # Sauvegarde des listings
        listings_df = pd.DataFrame(car_listings)
        listings_df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"💾 Sauvegarde des listings dans {output_file}")
        
        
    except Exception as e:
        print(f"❌ Erreur globale: {e}")
    finally:
        # Fermer le navigateur
        driver.quit()
        print("🏁 Programme terminé.")

if __name__ == "__main__":
    main()