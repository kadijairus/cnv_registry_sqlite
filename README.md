# CNV Register lokaalseks kasutamiseks

Töölaua rakendus, mis kasutab Pythonit, Tkinterit ja SQLite'i Koopiaarvu muutuste (CNV) andmete haldamiseks.

## Eeltingimused

*   Python 
*   Tkinter ja `sqlite3` on Pythoni standardselt kaasas

## Seadistamine ja käivitamine

### Variant 1. Käivita käsureal

1.  **Veendu, et kõik projekti failid** (`cnv_admin_gui.py`, `cnv_register_db.py`, `Registrid_cleaned.sql`) asuvad samas kaustas.
2.  **Andmebaasi loomine:** Ava terminal/käsurida projekti kaustas (näiteks kirjutades Windowsi arvutis aadressiribale cmd) ja käivita:
    ```bash
    python cnv_register_db.py
    ```
    *   See loob (või kirjutab üle olemasoleva) `cnv_register.db` faili, kasutades `Registrid_cleaned.sql` failis olevat skeemi.
3.  **Rakenduse käivitamine:** Käivita põhirakenduse skript:
    ```bash
    python cnv_admin_gui.py
    ```
### Variant 2. Käivita PyCharmis

1. **Käivita PyCharm**
2. Veendu, et sul on ligipääs projektile, seejärel Git clone URL: https://gitlab.cs.taltech.ee/kadi.jairus/iti0206_csv.git
3. **Andmebaasi loomine:** Käivita esmalt `cnv_register_db.py`
4. **Rakenduse käivitamine:** Käivita `cnv_admin_gui.py`

## Märkused

*   **Andmebaasi lähtestamine:** Uuesti alustamiseks käivita `python cnv_register_db.py`. Olemasolev `cnv_register.db` fail kustutatakse ja luuakse uuesti.
*   **Versioonihaldus:** Ära lisa `cnv_register.db` faili Giti. Lisa `*.db` oma `.gitignore` faili.
*   **Andmebaasi vaatamine (valikuline):** Faili `cnv_register.db` sisu saab vaadata mistahes standardse SQLite'i andmebaasibrauseriga (nt DB Browser for SQLite).