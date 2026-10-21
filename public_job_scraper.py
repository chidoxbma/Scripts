import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
import pandas as pd

# ---------------------------------------------------------
# 1. CONFIGURATION & HEADERS
# ---------------------------------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Strict filter keywords for Technician level (Bac+2 / Bac+3)
TECHNICIAN_KEYWORDS = [
    "technicien", "techniciens", "3ème grade", "3eme grade", 
    "4ème grade", "4eme grade", "dts", "dut", "bts", 
    "licence", "bac+2", "bac+3", "technicien spécialisé", "adjoit technique"
]

# Words to explicitly ignore (e.g., Engineers, Masters, PhDs, Executives)
EXCLUDE_KEYWORDS = ["ingénieur", "ingenieur", "master", "doctorat", "cadre", "architecte"]

# IT relevance keywords
IT_KEYWORDS = [
    "informatique", "système", "systèmes", "réseau", "réseaux", 
    "support", "développement", "développeur", "si", "data", 
    "sécurité", "cyber", "exploitation", "helpdesk", "maintenance"
]

# ---------------------------------------------------------
# 2. SCRAPER FOR EMPLOI-PUBLIC.MA (TECHNICIAN BAC+2 / BAC+3 ONLY)
# ---------------------------------------------------------
def fetch_emploi_public():
    print("[*] Scraping Emploi-Public.ma for Technician positions (Bac+2 / Bac+3)...")
    found_jobs = []
    
    search_keywords = ["informatique", "reseau", "systeme", "technicien"]

    for kw in search_keywords:
        url = f"https://www.emploi-public.ma/fr/concours-liste?key_word={kw}&type=1"
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                
                cards = soup.select(".card") or soup.find_all("div", class_=["annonce-item", "card-body"])
                if not cards:
                    cards = soup.find_all("div")

                for card in cards:
                    title_elem = card.find("h3") or card.find("a") or card.find("strong")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    title_lower = title.lower()

                    # 1. Must be IT-related
                    if not any(k in title_lower for k in IT_KEYWORDS):
                        continue

                    # 2. Must be a Technician / Bac+2 / Bac+3 role
                    is_technician = any(k in title_lower for k in TECHNICIAN_KEYWORDS)
                    
                    # 3. Must NOT be an Engineer / Master level
                    is_excluded = any(k in title_lower for k in EXCLUDE_KEYWORDS)

                    if is_technician and not is_excluded:
                        link_elem = card.find("a", href=True)
                        job_url = link_elem["href"] if link_elem else url
                        if job_url.startswith("/"):
                            job_url = "https://www.emploi-public.ma" + job_url

                        found_jobs.append({
                            "source": "Emploi-Public",
                            "title": title,
                            "job_url": job_url
                        })
        except Exception as e:
            print(f"[!] Error fetching kw '{kw}': {e}")

    df = pd.DataFrame(found_jobs)
    if not df.empty:
        df = df.drop_duplicates(subset=["title"])
    return df

# ---------------------------------------------------------
# 3. EMAIL NOTIFICATION FUNCTION
# ---------------------------------------------------------
def send_email_notification(df):
    if df.empty:
        print("[*] No matching public sector IT Technician jobs (Bac+2/Bac+3) found today.")
        return

    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL", sender_email)

    if not sender_email or not sender_password:
        print("[!] Email credentials not set. Printing results locally:")
        print(df[["source", "title", "job_url"]])
        return

    html_body = f"""
    <html>
      <body>
        <h2 style="color: #1a5276;">🏛️ {len(df)} Concours Technicien IT (Bac+2 / Bac+3) trouvés !</h2>
        <p>Voici les derniers concours publics correspondant aux profils Technicien / Adjoint Technique en informatique :</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; width: 100%;">
          <tr style="background-color: #1a5276; color: white;">
            <th>Source</th>
            <th>Intitulé du Poste / Concours (Technicien Bac+2 / Bac+3)</th>
            <th>Lien Offre</th>
          </tr>
    """

    for _, row in df.iterrows():
        source = row.get('source', 'Public')
        title = row.get('title', 'N/A')
        url = row.get('job_url', '#')

        html_body += f"""
          <tr>
            <td><span style="background: #e8f4f8; padding: 3px 6px; border-radius: 4px; font-size: 0.9em;">{source}</span></td>
            <td><b>{title}</b></td>
            <td><a href="{url}" style="color: #0066cc;">Voir Concours</a></td>
          </tr>
        """

    html_body += """
        </table>
        <p style="font-size: 0.8em; color: #7f8c8d; margin-top: 20px;">Source: Emploi-Public.ma (Filtre: Technicien Bac+2 / Bac+3)</p>
      </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = f"🏛️ Emploi-Public IT (Technicien Bac+2/3): {len(df)} Nouvelles Offres"
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg.set_content("Veuillez activer la vue HTML pour afficher le tableau.")
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print("[+] Email notification successfully sent!")
    except Exception as e:
        print(f"[!] Email error: {e}")

# ---------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------
if __name__ == "__main__":
    jobs_df = fetch_emploi_public()
    print(f"[*] Total unique Technician jobs found: {len(jobs_df)}")
    send_email_notification(jobs_df)
