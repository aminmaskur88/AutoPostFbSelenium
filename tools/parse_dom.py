from bs4 import BeautifulSoup
import re

with open('fb_dom_dump.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print("--- MENCARI TOMBOL JADWAL ---")
for el in soup.find_all(lambda tag: tag.name == 'div' and tag.has_attr('role') and tag['role'] == 'button'):
    text = el.text.strip()
    aria = el.get('aria-label', '')
    if 'jadwal' in text.lower() or 'jadwal' in aria.lower() or 'schedule' in text.lower() or 'schedule' in aria.lower():
        print(f"[{text[:30]}] Aria: {aria}")

print("\n--- MENCARI OPSI PENJADWALAN ---")
for el in soup.find_all(lambda tag: tag.name == 'div' and tag.has_attr('role') and tag['role'] == 'button'):
    text = el.text.strip()
    if 'opsi' in text.lower() or 'kalender' in text.lower():
        print(f"[{text[:30]}] Aria: {el.get('aria-label', '')}")
