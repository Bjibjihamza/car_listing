import time
import csv
import os
import re
import requests
import uuid
import urllib.parse
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


from kafka import KafkaProducer
import json

# Initialize Kafka Producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Convert to JSON format
)





def setup_driver():
    """Configure et initialise le driver Selenium."""
    options = Options()
    options.add_argument("--headless")  # Exécuter sans interface graphique
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")  # Réduire les logs inutiles

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def convert_relative_date(relative_date):
    """Convertit une date relative en date exacte.
    
    - Stocke l'heure uniquement pour minutes et heures
    - Ne garde que la date pour jours, mois, et années
    """
    now = datetime.now()

    # ✅ Cas "il y a quelques instants" → prendre l'heure actuelle
    if "quelques instants" in relative_date.lower():
        return now.strftime("%Y-%m-%d %H:%M:%S")  # Date et heure actuelles

    # ✅ Extraction du nombre (ex: "5" dans "il y a 5 minutes")
    match = re.search(r'(\d+)', relative_date)
    if match:
        num = int(match.group(1))  # Convertir en entier
    else:
        return "Date inconnue"  # Aucun nombre trouvé

    # ✅ Gestion des cas spécifiques
    if "minute" in relative_date:
        exact_date = now - timedelta(minutes=num)
        return exact_date.strftime("%Y-%m-%d %H:%M:%S")  # Garde l'heure

    elif "heure" in relative_date:
        exact_date = now - timedelta(hours=num)
        return exact_date.strftime("%Y-%m-%d %H:%M:%S")  # Garde l'heure

    elif "jour" in relative_date:
        exact_date = now - timedelta(days=num)
        return exact_date.strftime("%Y-%m-%d")  # Supprime l'heure

    elif "mois" in relative_date:
        exact_date = now - timedelta(days=30 * num)  # Approximation
        return exact_date.strftime("%Y-%m-%d")  # Supprime l'heure

    elif "an" in relative_date:
        exact_date = now - timedelta(days=365 * num)  # Approximation
        return exact_date.strftime("%Y-%m-%d")  # Supprime l'heure

    else:
        return "Date inconnue"  # Cas non prévu

def create_folder_name(title, idx):
    """Crée un nom de dossier valide pour stocker les images d'une annonce."""
    # Nettoyer le titre pour obtenir un nom de dossier valide
    folder_name = re.sub(r'[^\w\s-]', '', title)  # Supprimer les caractères non alphanumériques
    folder_name = re.sub(r'\s+', '_', folder_name)  # Remplacer les espaces par des underscores
    folder_name = folder_name[:50]  # Limiter la longueur
    
    # Ajouter l'ID pour garantir l'unicité
    folder_name = f"{idx}_{folder_name}"
    
    return folder_name




def scrape_avito(pages=1):
    """Scrape the car listings on Avito across multiple pages."""
    base_url = "https://www.avito.ma/fr/maroc/v%C3%A9hicules"
    driver = setup_driver()
    
    data = []
    listing_id_counter = 1  # Initialize the global ID counter

    # Loop through the first `pages` pages
    for page in range(1, pages + 1):
        url = f"{base_url}?o={page}"
        print(f"🔎 Scraping page {page}: {url}")
        
        driver.get(url)
        driver.set_page_load_timeout(180)  # Increase timeout duration

        # ✅ Wait for the page to load correctly
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "sc-1nre5ec-1")))
        except Exception as e:
            print(f"❌ Timeout: Impossible de charger la page ({e})")
            driver.quit()
            return None

        try:
            # Ensure all content is loaded by scrolling to the bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # Wait for additional content to load

            # **Find the main container**
            main_container = driver.find_element(By.CLASS_NAME, "sc-1nre5ec-1")

            # **Get all listings on the page**
            listings = main_container.find_elements(By.CSS_SELECTOR, "a.sc-1jge648-0.jZXrfL")

            if not listings:
                print("❌ Aucune annonce trouvée ! Vérifie si le site a changé.")
                driver.quit()
                return None

            print(f"✅ {len(listings)} annonces trouvées sur la page {page} !")

            # **Iterate through the listings**
            for listing in listings:
                try:
                    # **Title**
                    title = listing.find_element(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.iHApav").text.strip() if listing.find_elements(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.iHApav") else "N/A"

                    # **Price**
                    price = listing.find_element(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.dJAfqm").text.strip() if listing.find_elements(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.dJAfqm") else "Prix non spécifié"

                    # **Publication date**
                    pub_date_raw = listing.find_element(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.layWaX").text.strip() if listing.find_elements(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.layWaX") else "N/A"
                    pub_date = convert_relative_date(pub_date_raw)  # Convert to exact date

                    # **Year**
                    year = listing.find_element(By.XPATH, ".//span[contains(text(),'20')]").text.strip() if listing.find_elements(By.XPATH, ".//span[contains(text(),'20')]") else "N/A"

                    # **Fuel type**
                    fuel_type = listing.find_element(By.XPATH, ".//span[contains(text(),'Essence') or contains(text(),'Diesel') or contains(text(),'Hybride') or contains(text(),'Électrique')]").text.strip() if listing.find_elements(By.XPATH, ".//span[contains(text(),'Essence') or contains(text(),'Diesel') or contains(text(),'Hybride') or contains(text(),'Électrique')]") else "N/A"

                    # **Transmission**
                    transmission = listing.find_element(By.XPATH, ".//span[contains(text(),'Automatique') or contains(text(),'Manuelle')]").text.strip() if listing.find_elements(By.XPATH, ".//span[contains(text(),'Automatique') or contains(text(),'Manuelle')]") else "N/A"

                    # **Listing link**
                    link = listing.get_attribute("href") if listing.get_attribute("href") else "N/A"

                    # **Creator**
                    creator = "Particulier"
                    try:
                        creator_element = listing.find_element(By.CSS_SELECTOR, "p.sc-1x0vz2r-0.hNCqYw.sc-1wnmz4-5.dXzQnB")
                        creator = creator_element.text.strip() if creator_element else "Particulier"
                    except:
                        pass  # If no name found, set to "Particulier" by default

                    # Create folder name for this listing
                    folder_name = create_folder_name(title, listing_id_counter)



                    # ✅ Send Data to Kafka
                    car_data = {
                        "id": listing_id_counter,
                        "title": title,
                        "price": price,
                        "pub_date": pub_date,
                        "year": year,
                        "fuel_type": fuel_type,
                        "transmission": transmission,
                        "creator": creator,
                        "link": link,
                        "folder_name": folder_name
                    }

                    producer.send("avito_topic", car_data)
                    producer.flush()
                    print(f"🚀 Sent to Kafka: {car_data}")




                    # **Save data**
                    data.append([listing_id_counter, title, price, pub_date, year, fuel_type, transmission, creator, link, folder_name])

                    listing_id_counter += 1  # Increment the global counter after each listing

                except Exception as e:
                    print(f"⚠️ Erreur avec l'annonce: {e}")

        except Exception as e:
            print(f"❌ Erreur lors de l'extraction de la page {page}: {e}")

    driver.quit()

    return data



def save_to_csv(data, filename):
    """Sauvegarde les données dans un fichier CSV dans ../data/avito/."""
    output_folder = os.path.join("..", "data", "avito")  # New directory: ../data/avito/
    os.makedirs(output_folder, exist_ok=True)  # Create if not exists
    output_file = os.path.join(output_folder, filename)

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Titre", "Prix", "Date de publication", "Année", "Type de carburant", "Transmission", "Créateur", "URL de l'annonce", "Dossier d'images"])
        writer.writerows(data)

    print(f"✅ Données sauvegardées dans {output_file}")
    return output_file





def download_image(image_url, folder_path, image_name):
    """Télécharge une image et la sauvegarde dans le dossier spécifié."""
    try:
        # Ajouter des en-têtes pour simuler un navigateur
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(image_url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        
        # Déterminer l'extension de fichier basée sur le Content-Type
        content_type = response.headers.get('Content-Type', '')
        extension = '.jpg'  # Par défaut
        if 'png' in content_type:
            extension = '.png'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            extension = '.jpg'
        
        image_path = os.path.join(folder_path, f"{image_name}{extension}")
        
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return os.path.basename(image_path)  # Retourne le nom du fichier sauvegardé
    
    except Exception as e:
        print(f"❌ Erreur de téléchargement d'image: {e}")
        return None



def scrape_details(url, driver, listing_id, folder_name):
    """Access a car listing page and scrape additional details including images."""
    driver.get(url)
    time.sleep(3)  # Allow the page to load
    
    # Create folder for this listing's images
    images_base_folder = os.path.join("..", "data", "avito", "images")
    os.makedirs(images_base_folder, exist_ok=True)
    
    listing_folder = os.path.join(images_base_folder, folder_name)
    os.makedirs(listing_folder, exist_ok=True)
    
    # Initialize images list
    images_paths = []
    
    try:
        # ✅ Scroll down to load all content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # ✅ DOWNLOAD IMAGES
        try:
            # Find all images in the slider
            image_elements = driver.find_elements(By.CSS_SELECTOR, "div.picture img.sc-1gjavk-0")
            
            if image_elements:
                print(f"✅ Found {len(image_elements)} images for listing {listing_id}")
                
                for i, img in enumerate(image_elements):
                    try:
                        img_src = img.get_attribute("src")
                        if img_src:
                            # Télécharger l'image et obtenir le chemin relatif
                            image_filename = download_image(img_src, listing_folder, f"image_{i+1}")
                            if image_filename:
                                rel_path = os.path.join(folder_name, image_filename)
                                images_paths.append(rel_path)
                                print(f"✅ Downloaded image {i+1}/{len(image_elements)} for listing {listing_id}")
                    except Exception as e:
                        print(f"⚠️ Error downloading image {i+1} for listing {listing_id}: {e}")
            else:
                print(f"⚠️ No images found for listing {listing_id}")
        except Exception as e:
            print(f"❌ Error processing images for listing {listing_id}: {e}")

        # ✅ Click on "Show more details" if available
        try:
            show_more_button = driver.find_element(By.XPATH, "//button[contains(., 'Afficher plus de détails')]")
            show_more_button.click()
            time.sleep(2)  # Wait for additional details to load
        except:
            pass  # If the button is not found, continue normally

        # ✅ Ensure details section is present
        try:
            details_section = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='sc-qmn92k-0 cjptpz']"))
            )
        except:
            print(f"⚠️ Could not find details section for {url}")
            return ["N/A"] * 12 + [folder_name]  # Retourner le nom du dossier au lieu des chemins d'images

        # ✅ Extract details into a dictionary
        details = {}
        details_list = details_section.find_elements(By.XPATH, ".//li")

        for item in details_list:
            try:
                key_element = item.find_element(By.XPATH, ".//span[@class='sc-1x0vz2r-0 jZyObG']")
                value_element = item.find_element(By.XPATH, ".//span[@class='sc-1x0vz2r-0 gSLYtF']")
                
                key = key_element.text.strip()
                value = value_element.text.strip()
                details[key] = value
            except:
                continue  # Skip items that cause issues

        # ✅ Extract specific values in English
        car_type = details.get("Type", "N/A")
        location = details.get("Secteur", "N/A")
        mileage = details.get("Kilométrage", "N/A")
        brand = details.get("Marque", "N/A")
        model = details.get("Modèle", "N/A")
        doors = details.get("Nombre de portes", "N/A")
        origin = details.get("Origine", "N/A")
        first_hand = details.get("Première main", "N/A")
        fiscal_power = details.get("Puissance fiscale", "N/A")
        condition = details.get("État", "N/A")

        # ✅ Extract Equipment List
        try:
            equipment_section = driver.find_element(By.XPATH, "//div[@class='sc-1g3sn3w-15 evEiLa']")
            equipment_list = equipment_section.find_elements(By.XPATH, ".//span[@class='sc-1x0vz2r-0 bXFCIH']")
            equipments = [eq.text.strip() for eq in equipment_list]
        except:
            equipments = ["N/A"]  # If no equipment is found

        equipment_text = ", ".join(equipments)

        # ✅ Extract Seller's City
        try:
            city_section = driver.find_element(By.XPATH, "//div[@class='sc-1g3sn3w-7 bNWHpB']")
            city_element = city_section.find_element(By.XPATH, ".//span[@class='sc-1x0vz2r-0 iotEHk']")
            seller_city = city_element.text.strip()
        except:
            seller_city = "N/A"  # If city is not found

        # Renvoyer le nom du dossier au lieu de la liste des chemins d'images
        return [car_type, location, mileage, brand, model, doors, origin, first_hand, fiscal_power, condition, equipment_text, seller_city, folder_name]

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return ["N/A"] * 12 + [folder_name]  # Retourner le nom du dossier en cas d'erreur

def process_detailed_data(basic_data, output_file):
    """Process the basic data to get detailed information for each listing."""
    driver = setup_driver()

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    new_headers = [
        "ID", "Titre", "Prix", "Date de publication", "Année", "Type de carburant", "Transmission", "Créateur",
        "Type de véhicule", "Secteur", "Kilométrage", "Marque", "Modèle", "Nombre de portes", "Origine", 
        "Première main", "Puissance fiscale", "État", "Équipements", "Ville du vendeur", "Dossier d'images"
    ]

    detailed_data = [new_headers]  # Ensure new headers are used

    for idx, row in enumerate(basic_data, start=1):
        url = row[8]  # URL is at index 8
        folder_name = row[9]  # Folder name is at index 9
        print(f"🔎 Scraping listing {idx}/{len(basic_data)} : {url}")

        details = scrape_details(url, driver, idx, folder_name)

        # Merge all attributes
        combined_data = row[:8] + details  # Ensure correct ordering

        detailed_data.append(combined_data)

    driver.quit()

    # ✅ Save the extracted details
    print(f"📂 Enregistrement du fichier CSV détaillé dans : {output_file}")

    try:
        with open(output_file, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerows(detailed_data)

        print(f"✅ Fichier CSV détaillé sauvegardé dans {output_file}")

    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement des détails : {e}")
        

def main():
    """Main function to run the complete scraper."""
    print("🚗 Starting Avito car listings scraper...")
    
    # Step 1: Scrape basic listings
    print("\n📋 STEP 1: Scraping basic car listings...")
    basic_data = scrape_avito(pages=1)
    
    if basic_data is None or len(basic_data) == 0:
        print("❌ No data found. Exiting program.")
        return
    
    # Step 2: Save basic listings to CSV
    basic_csv = save_to_csv(basic_data, "avito_listings.csv")
    
    # Step 3: Get detailed information for each listing and download images
    print("\n🔍 STEP 2: Collecting detailed information and downloading images for each listing...")
    detailed_csv = os.path.join("../data/avito", "avito_details.csv")
    process_detailed_data(basic_data, detailed_csv)
    
    print("\n✅ SCRAPING COMPLETED SUCCESSFULLY!")
    print(f"Basic listings: {basic_csv}")
    print(f"Detailed information: {detailed_csv}")
    print(f"Images downloaded to: data/images/[listing_folders]")

if __name__ == "__main__":
    main()