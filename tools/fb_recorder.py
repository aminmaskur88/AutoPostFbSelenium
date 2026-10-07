import os
import sys
import time
import json
from selenium.webdriver.support.ui import WebDriverWait

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.utils import setup_driver

def get_xpath_script():
    return """
    window.lastClickedElement = null;
    
    function getXPath(element) {
        if (element.id !== '')
            return 'id("' + element.id + '")';
        if (element === document.body)
            return element.tagName;

        var ix = 0;
        var siblings = element.parentNode.childNodes;
        for (var i = 0; i < siblings.length; i++) {
            var sibling = siblings[i];
            if (sibling === element)
                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                ix++;
        }
    }

    document.addEventListener('keydown', function(e) {
        // Hanya bertindak saat user menekan ENTER di elemen yang sedang difokus
        if (e.key === 'Enter') {
            setTimeout(() => {
                recordElement(document.activeElement, 'Keyboard (Enter)');
            }, 50);
        }
    }, true);
    
    function recordElement(el, actionType) {
        if (!el) return;
        let xpath = getXPath(el);
        let tag = el.tagName.toLowerCase();
        let aria = el.getAttribute('aria-label') || '';
        let text = el.innerText || el.value || '';
        if (text.length > 50) text = text.substring(0, 50) + '...';
        
        window.lastClickedElement = {
            action: actionType,
            xpath: xpath,
            tag: tag,
            aria: aria,
            text: text
        };
    }
    """

def main():
    print("=== FACEBOOK CLICK RECORDER ===")
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fb_profiles'))
    profiles = [f for f in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, f))]
    
    for i, p in enumerate(profiles, 1):
        print(f"{i}. {p}")
        
    pilihan = input("Masukkan nomor profil: ").strip()
    try:
        profile_name = profiles[int(pilihan)-1]
    except:
        print("Pilihan tidak valid.")
        return
        
    profile_path = os.path.join(profile_dir, profile_name)
    driver = setup_driver(profile_path, headless=False)
    
    print("\nMembuka Facebook...")
    try:
        driver.get("https://www.facebook.com/")
    except: pass
    
    recorded_steps = []
    print("\n" + "="*50)
    print("RECORDER AKTIF!")
    print("Silakan klik/tab di browser. Setelah selesai, ketik 'exit' di terminal.")
    print("="*50 + "\n")

    try:
        while True:
            # Selalu pastikan script kita terinjeksi (berjaga-jaga jika FB me-reload halaman)
            try:
                is_injected = driver.execute_script("return typeof window.lastClickedElement !== 'undefined';")
                if not is_injected:
                    driver.execute_script(get_xpath_script())
            except Exception:
                time.sleep(1)
                continue
                
            # Cek apakah ada elemen baru yang diklik (dari JS)
            try:
                clicked = driver.execute_script("""
                    let data = window.lastClickedElement;
                    if(data) window.lastClickedElement = null; // reset
                    return data;
                """)
            except Exception as js_err:
                time.sleep(1)
                continue
            
            if clicked:
                action = clicked.get('action', 'Mouse Click')
                print(f"\n[+] Aksi terdeteksi: {action}")
                print(f"    - Teks  : {clicked.get('text', '')}")
                print(f"    - Aria  : {clicked.get('aria', '')}")
                print(f"    - Tag   : {clicked.get('tag', '')}")
                print(f"    - XPath : {clicked.get('xpath', '')}")
                
                step_name = input("\n> Langkah apa ini? (ketik 'exit' untuk simpan & keluar, ENTER untuk abaikan): ").strip()
                
                if step_name.lower() == 'exit':
                    break
                
                if step_name != "":
                    clicked['step_name'] = step_name
                    recorded_steps.append(clicked)
                    print(f"✔️ Langkah '{step_name}' tersimpan!\nLanjut klik elemen berikutnya di browser...")
                else:
                    print("❌ Diabaikan. Silakan klik elemen berikutnya di browser.")
                    
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Script berhenti karena error:\n{traceback.format_exc()}")
        input("Tekan ENTER untuk keluar...")
    finally:
        if recorded_steps:
            save_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'fb_new_ui_steps.json'))
            with open(save_path, 'w') as f:
                json.dump(recorded_steps, f, indent=4)
            print(f"\n✅ Data rekaman disimpan di: {save_path}")
        
        print("Menutup browser...")
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
