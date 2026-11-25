""""
Run SQLite database GUI for CNV Register administration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import traceback # For detailed error logging
import cnv_register_db as db # Import the data access layer module
import cnv_backup

class CNVAdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CNV register - Administraatori vaade (sisse logitud)")
        self.root.geometry("950x650")

        # --- Database Connection ---
        self.conn = None
        self.cursor = None
        self.connect_to_database() # Initialize connection and cursor

        # --- Load Classifiers (Data for Comboboxes etc.) ---
        self.kromosoomid = {}
        self.koopiaarvud = {}
        self.tahendused = {}
        self.paritolud = {}
        self.cnv_seisundid = {}
        self.kromosoomid_rev = {}
        self.koopiaarvud_rev = {}
        self.tahendused_rev = {}
        self.paritolud_rev = {}
        self.cnv_seisundid_rev = {}

        if self.conn and self.cursor:
            self.load_classifiers()
        else:
            # Show error if connection failed during init
             messagebox.showerror("Andmebaasi viga",
                                  f"Andmebaasi ({db.DB_FILE}) ühendust ei õnnestunud luua.\n"
                                  "Klassifikaatorid lisada. Rakendus ei pruugi töötada.")
             # Optionally disable UI elements or exit
             # self.root.destroy()

        self.selected_cnv_id = None # Holds the ID of the selected CNV in the list
        self.sort_column = None     # Track last sorted column for Treeview sorting
        self.sort_direction = False # Track sort direction (False=ASC, True=DESC)

        # --- Create GUI Widgets ---
        self.create_widgets()

        # --- Populate Initial List ---
        if self.conn and self.cursor:
             # Populate with active CNVs, data arrives sorted from DB
             self.populate_cnv_list(view_type='active')
        else:
             print("Skipping initial CNV list population due to connection error.")

        # Handle window closing event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --------------------------------------------------------------------------
    # DATABASE & CLASSIFIER HANDLING
    # --------------------------------------------------------------------------

    def connect_to_database(self):
        """Attempts to connect to the database using the function from cnv_register_db."""
        print("Attempting to connect to database...")
        self.conn, self.cursor = db.db_connect()
        if not self.conn:
            print("Database connection failed in GUI.")
        else:
             print("Database connection successful in GUI.")

    def load_classifiers(self):
        """Loads classification data from the database into dictionaries."""
        print("Loading classifiers from database...")
        if not self.cursor:
             print("ERROR: Cannot load classifiers, no database cursor.")
             return
        try:
            # Kromosoom
            krom_data = db.get_active_classifications(self.cursor, 'Kromosoom', 'kromosoom_kood', 'kromosoom_nimi')
            self.kromosoomid = {row['kromosoom_nimi']: row['kromosoom_kood'] for row in krom_data}
            self.kromosoomid_rev = {v: k for k, v in self.kromosoomid.items()}

            # Koopiaarv (needs value and name)
            koop_data = db.get_active_classifications(self.cursor, 'Koopiaarv', 'koopiaarv_kood', 'koopiaarv_nimi', other_cols=['koopiaarv_vaartus'])
            self.koopiaarvud = {f"{row['koopiaarv_vaartus']} ({row['koopiaarv_nimi']})": row['koopiaarv_kood'] for row in koop_data}
            self.koopiaarvud_rev = {v: k for k, v in self.koopiaarvud.items()}

            # Tahendus
            tahendus_data = db.get_active_classifications(self.cursor, 'Tahendus', 'tahendus_kood', 'tahendus_nimi')
            self.tahendused = {row['tahendus_nimi']: row['tahendus_kood'] for row in tahendus_data}
            self.tahendused_rev = {v: k for k, v in self.tahendused.items()}

            # Paritolu
            paritolu_data = db.get_active_classifications(self.cursor, 'Paritolu', 'paritolu_kood', 'paritolu_nimi')
            self.paritolud = {row['paritolu_nimi']: row['paritolu_kood'] for row in paritolu_data}
            self.paritolud_rev = {v: k for k, v in self.paritolud.items()}

            # CNV_seisund (Fetch all states, including inactive like 'artefakt')
            try:
                self.cursor.execute("SELECT CNV_seisund_kood, CNV_seisund_nimi FROM CNV_seisund ORDER BY CNV_seisund_nimi;")
                all_seisund_data = self.cursor.fetchall()
                self.cnv_seisundid = {row['CNV_seisund_nimi']: row['CNV_seisund_kood'] for row in all_seisund_data}
                self.cnv_seisundid_rev = {v: k for k, v in self.cnv_seisundid.items()}
            except sqlite3.Error as e:
                 print(f"ERROR fetching all CNV_seisund: {e}")
                 messagebox.showerror("Klassifikaatorite viga", "Ei õnnestunud CNV seisundit laadida.")

            print("Classifiers loaded.")

        except Exception as e:
            messagebox.showerror("Klassifikaatorite viga", f"Ei õnnestunud laadida klassifikaatoreid: {e}")
            traceback.print_exc()

    # --------------------------------------------------------------------------
    # WIDGET CREATION
    # --------------------------------------------------------------------------

    def create_widgets(self):
        """Creates all the GUI widgets."""
        # --- Frame Setup ---
        controls_frame = ttk.LabelFrame(self.root, text="CNV andmed ja tegevused")
        controls_frame.pack(padx=10, pady=(5,0), fill=tk.X) # Less padding top

        # Assign the list frame to self.list_frame so its title can be changed
        self.list_frame = ttk.LabelFrame(self.root, text="CNV nimekiri") # Initial title
        self.list_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # --- Input Fields and Labels Frame ---
        form_frame = ttk.Frame(controls_frame)
        form_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        row_num = 0
        # Row 0
        ttk.Label(form_frame, text="Analüüsi DNA kood:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        self.dna_kood_entry = ttk.Entry(form_frame, width=15)
        self.dna_kood_entry.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)
        ttk.Label(form_frame, text="Kromosoom:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.kromosoom_combo = ttk.Combobox(form_frame,
                                            values=sorted(list(self.kromosoomid.keys()), key=lambda x: int(x) if x.isdigit() else ord(x[0])),
                                            width=5, state="readonly")
        self.kromosoom_combo.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 1
        ttk.Label(form_frame, text="Alguskoordinaat:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        self.algus_entry = ttk.Entry(form_frame, width=15)
        self.algus_entry.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)
        ttk.Label(form_frame, text="Lõppkoordinaat:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.lopp_entry = ttk.Entry(form_frame, width=15)
        self.lopp_entry.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 2
        ttk.Label(form_frame, text="Koopiaarv:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        koopiaarv_sorted_keys = sorted(self.koopiaarvud.keys(), key=lambda x: int(x.split()[0]))
        self.koopiaarv_combo = ttk.Combobox(form_frame, values=koopiaarv_sorted_keys, width=20, state="readonly")
        self.koopiaarv_combo.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W) # Removed columnspan
        ttk.Label(form_frame, text="Tähendus:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.tahendus_combo = ttk.Combobox(form_frame, values=sorted(list(self.tahendused.keys())), width=15, state="readonly")
        self.tahendus_combo.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 3
        ttk.Label(form_frame, text="Päritolu:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        self.paritolu_combo = ttk.Combobox(form_frame, values=sorted(list(self.paritolud.keys())), width=15, state="readonly")
        self.paritolu_combo.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)

        # --- Action Buttons Frame ---
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(side=tk.RIGHT, padx=5, pady=5, anchor=tk.N) # Anchor North

        self.add_button = ttk.Button(button_frame, text="Lisa CNV", command=self.add_cnv_gui)
        self.add_button.pack(fill=tk.X, pady=2)
        # Changed button text
        self.update_button = ttk.Button(button_frame, text="Muuda CNVd", command=self.update_cnv_gui, state=tk.DISABLED)
        self.update_button.pack(fill=tk.X, pady=2)
        self.set_artefact_button = ttk.Button(button_frame, text="Märgi Artefaktiks", command=self.set_cnv_state_gui_artefact, state=tk.DISABLED)
        self.set_artefact_button.pack(fill=tk.X, pady=2)
        self.set_active_button = ttk.Button(button_frame, text="Märgi Aktiivseks", command=self.set_cnv_state_gui_active, state=tk.DISABLED)
        self.set_active_button.pack(fill=tk.X, pady=2)
        self.clear_button = ttk.Button(button_frame, text="Tühjenda Vorm", command=self.clear_form)
        self.clear_button.pack(fill=tk.X, pady=2)

        # --- List View (Treeview) ---
        # Define ALL columns using DB names; this tuple is used consistently
        self.all_db_columns = (
            "cnv_id", "DNA_kood", "kromosoom_nimi", "alguskoordinaat",
            "loppkoordinaat", "koopiaarv_vaartus", "tahendus_nimi",
            "paritolu_nimi", "CNV_seisund_nimi"
        )
        # Create Treeview inside self.list_frame
        self.cnv_tree = ttk.Treeview(self.list_frame, columns=self.all_db_columns, show="headings")

        # Configure ALL headings and columns, bind click for sorting
        for col_id in self.all_db_columns:
            # Bind heading click to sorting function
            self.cnv_tree.heading(col_id, text=col_id,
                                  command=lambda c=col_id: self.sort_treeview_column(c))
            # Set widths, anchor, and stretch properties
            if col_id == "cnv_id": width = 0; anchor = tk.W; stretch = tk.NO # Hide cnv_id
            elif col_id == "DNA_kood": width = 90; anchor = tk.W; stretch = tk.YES
            elif col_id == "kromosoom_nimi": width = 50; anchor = tk.CENTER; stretch = tk.YES
            elif col_id == "alguskoordinaat": width = 100; anchor = tk.E; stretch = tk.YES
            elif col_id == "loppkoordinaat": width = 100; anchor = tk.E; stretch = tk.YES
            elif col_id == "koopiaarv_vaartus": width = 60; anchor = tk.CENTER; stretch = tk.YES
            elif col_id == "tahendus_nimi": width = 120; anchor = tk.W; stretch = tk.YES
            elif col_id == "paritolu_nimi": width = 100; anchor = tk.W; stretch = tk.YES
            elif col_id == "CNV_seisund_nimi": width = 80; anchor = tk.W; stretch = tk.YES
            else: width = 80; anchor = tk.W; stretch = tk.YES # Default
            self.cnv_tree.column(col_id, width=width, anchor=anchor, stretch=stretch)

        # Scrollbars (inside self.list_frame)
        vsb = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.cnv_tree.yview)
        hsb = ttk.Scrollbar(self.list_frame, orient="horizontal", command=self.cnv_tree.xview)
        self.cnv_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.cnv_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True) # Pack Treeview first

        # Event binding for selection
        self.cnv_tree.bind("<<TreeviewSelect>>", self.on_cnv_select)

        # --- List Control Buttons Frame (inside self.list_frame) ---
        list_control_frame = ttk.Frame(self.list_frame)
        list_control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0)) # Pack at bottom

        ttk.Label(list_control_frame, text="Kuva analüüsi DNA:").pack(side=tk.LEFT, padx=(0,2))
        self.view_dna_entry = ttk.Entry(list_control_frame, width=15)
        self.view_dna_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(list_control_frame, text="Kuva Analüüsi CNVd", command=self.populate_cnv_list_by_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_control_frame, text="Kuva Kõik Aktiivsed", command=lambda: self.populate_cnv_list(view_type='active')).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_control_frame, text="Ekspordi Aktiivsed (BED)", command=self.export_active_cnvs).pack(side=tk.LEFT, padx=5)


    # --------------------------------------------------------------------------
    # GUI ACTIONS & EVENT HANDLERS
    # --------------------------------------------------------------------------

    def sort_treeview_column(self, col_id):
        """Sorts the Treeview data based on the clicked column header."""
        items = self.cnv_tree.get_children('')
        if not items: return # Nothing to sort

        # Create list of tuples: (value_to_sort_by, item_id)
        data_to_sort = []
        try:
            col_index = self.all_db_columns.index(col_id) # Find index for the column identifier
        except ValueError:
            print(f"Error: Column '{col_id}' not found in self.all_db_columns for sorting.")
            return

        for item_id in items:
            value = self.cnv_tree.item(item_id)['values'][col_index]
            data_to_sort.append((value, item_id))

        # Define a type-aware sorting key function based on column ID
        def sort_key(item):
            val = item[0] # The value from the column
            numeric_cols = ['cnv_id', 'alguskoordinaat', 'loppkoordinaat', 'koopiaarv_vaartus']
            chr_cols = ['kromosoom_nimi']

            if col_id in numeric_cols:
                try: # Attempt numeric sort, treat non-numeric/empty as very small
                    return float(val) if isinstance(val, (int, float)) or (isinstance(val, str) and val.strip()) else float('-inf')
                except (ValueError, TypeError): return float('-inf')
            elif col_id in chr_cols: # Special sort for chromosomes
                 if isinstance(val, str):
                     if val.isdigit(): return (0, int(val)) # Numeric chromosomes first
                     elif val.upper() == 'X': return (1, 0) # X after numbers
                     elif val.upper() == 'Y': return (2, 0) # Y after X
                     else: return (3, val.lower()) # Other strings alphabetically
                 else: return (4, str(val).lower()) # Non-strings last
            else: # Default: case-insensitive string sort
                return str(val).lower()

        # Determine sort direction
        reverse_order = False
        if col_id == self.sort_column: reverse_order = not self.sort_direction
        else: reverse_order = False # Default to ascending

        # Sort the data
        data_to_sort.sort(key=sort_key, reverse=reverse_order)

        # Reorder items in the treeview
        for index, (val, item_id) in enumerate(data_to_sort):
            self.cnv_tree.move(item_id, '', index)

        # Update sort state
        self.sort_column = col_id
        self.sort_direction = reverse_order

    def clear_form(self):
        """Clears input fields and selection state."""
        self.selected_cnv_id = None
        self.dna_kood_entry.config(state=tk.NORMAL) # Enable before clearing
        self.dna_kood_entry.delete(0, tk.END)
        self.algus_entry.delete(0, tk.END)
        self.lopp_entry.delete(0, tk.END)
        self.kromosoom_combo.set('')
        self.koopiaarv_combo.set('')
        self.tahendus_combo.set('')
        self.paritolu_combo.set('')
        # Reset DNA entry state based on whether a selection is active (it's not after clear)
        # self.dna_kood_entry.config(state=tk.NORMAL) # Keep enabled for adding

        # Clear Treeview selection
        selection = self.cnv_tree.selection()
        if selection: self.cnv_tree.selection_remove(selection)

        # Reset button states
        self.update_button.config(state=tk.DISABLED)
        self.set_artefact_button.config(state=tk.DISABLED)
        self.set_active_button.config(state=tk.DISABLED)
        self.add_button.config(state=tk.NORMAL) # Enable add button

    def populate_cnv_list(self, cnvs=None, view_type='active'):
        """Populates the Treeview list with CNV data and adjusts displayed columns."""
        if not self.cursor:
            print("ERROR: Cannot populate CNV list, no database cursor.")
            return

        # Clear old entries
        for i in self.cnv_tree.get_children():
            self.cnv_tree.delete(i)

        # Determine which columns to SHOW and fetch data if needed
        if view_type == 'active':
            # Columns to display for the "All Active" view
            display_columns_subset = (
                "DNA_kood", "kromosoom_nimi", "alguskoordinaat", "loppkoordinaat",
                "koopiaarv_vaartus", "tahendus_nimi", "paritolu_nimi", "CNV_seisund_nimi"
            ) # Exclude cnv_id from visible
            # Reset list frame title
            self.list_frame.config(text="Aktiivsete CNVde Nimekiri") # More descriptive title
            if cnvs is None:
                cnvs = db.get_active_cnvs_display(self.cursor) # Fetches state too
        elif view_type == 'single_analysis':
            # Columns to display for the "Single Analysis" view (hide DNA_kood)
            display_columns_subset = (
                "kromosoom_nimi", "alguskoordinaat", "loppkoordinaat", "koopiaarv_vaartus",
                "tahendus_nimi", "paritolu_nimi", "CNV_seisund_nimi"
            ) # Exclude cnv_id and DNA_kood from visible
        else:
            # Unknown view type
            print(f"Unknown view_type '{view_type}', showing empty.")
            display_columns_subset = () # Show nothing visible
            self.list_frame.config(text="CNV nimekiri") # Reset title
            cnvs = []

        # Configure which columns are VISIBLE using displaycolumns
        self.cnv_tree['displaycolumns'] = display_columns_subset

        # Add new entries
        if cnvs:
            for cnv_row in cnvs:
                try:
                    row_keys = cnv_row.keys()
                    # Create tuple with values for ALL defined columns (self.all_db_columns)
                    values_tuple = tuple(cnv_row[col_id] if col_id in row_keys else '' for col_id in self.all_db_columns)
                    self.cnv_tree.insert("", tk.END, values=values_tuple, iid=cnv_row['cnv_id']) # Use cnv_id as internal item ID
                except Exception as e:
                    print(f"Error processing/inserting row into Treeview: {e}, Row data: {dict(cnv_row)}")
        else:
            print("No CNVs to display in the list.")

        # Reset sort state when list is repopulated
        self.sort_column = None
        self.sort_direction = False

    def populate_cnv_list_by_analysis(self):
        """Fetches and displays CNVs for a specific analysis DNA code."""
        if not self.cursor: messagebox.showerror("Viga", "Andmebaasi ühendust ei õnnestunud luua."); return
        dna_kood = self.view_dna_entry.get().strip()
        if not dna_kood: messagebox.showwarning("Sisend puudu", "Otsimiseks sisesta analüüsi kood."); return

        analysis_details = db.get_analysis_details_by_dna(self.cursor, dna_kood)
        if not analysis_details:
            messagebox.showinfo("Viga", f"Analüüsi koodiga '{dna_kood}' ei leitud.")
            self.list_frame.config(text="CNV nimekiri") # Reset title
            self.populate_cnv_list([], view_type='single_analysis')
            return

        analyys_id = analysis_details['analyys_id']
        print(f"Fetching CNVs for analysis ID: {analyys_id} (DNA: {dna_kood})")
        cnvs = db.get_cnvs_for_analysis_display(self.cursor, analyys_id)
        # Update list frame title BEFORE populating
        self.list_frame.config(text=f"{dna_kood} CNV nimekiri")
        # Call populate_cnv_list, passing data and view type
        self.populate_cnv_list(cnvs, view_type='single_analysis')
        if not cnvs: messagebox.showinfo("Tulemusteta", f"Ei õnnestunud leida ühtegi CNVd DNA koodiga '{dna_kood}'.")


    def on_cnv_select(self, event):
        """Handles selection change in the Treeview."""
        if not self.cursor: return
        selection = self.cnv_tree.selection()
        if not selection:
            self.clear_form(); return

        # Use the internal item ID (iid) which we set to cnv_id during insertion
        selected_iid = selection[0]
        try:
            self.selected_cnv_id = int(selected_iid) # iid IS the cnv_id
            print(f"CNV selected, ID: {self.selected_cnv_id}")

            details = db.get_cnv_details_for_edit(self.cursor, self.selected_cnv_id)
            if not details:
                messagebox.showerror("Viga", f"Ei õnnestunud laadida selle CNV andmeid: {self.selected_cnv_id}")
                self.clear_form(); return

            # Fill form fields
            self.dna_kood_entry.config(state=tk.NORMAL)
            self.dna_kood_entry.delete(0, tk.END)
            self.dna_kood_entry.insert(0, details['DNA_kood'])
            self.dna_kood_entry.config(state=tk.DISABLED)
            self.algus_entry.delete(0, tk.END); self.algus_entry.insert(0, details['alguskoordinaat'])
            self.lopp_entry.delete(0, tk.END); self.lopp_entry.insert(0, details['loppkoordinaat'])
            self.kromosoom_combo.set(self.kromosoomid_rev.get(details['kromosoom_kood'], ''))
            self.koopiaarv_combo.set(self.koopiaarvud_rev.get(details['koopiaarv_kood'], ''))
            self.tahendus_combo.set(self.tahendused_rev.get(details['tahendus_kood'], ''))
            self.paritolu_combo.set(self.paritolud_rev.get(details['paritolu_kood'], ''))

            # Update button states
            self.add_button.config(state=tk.DISABLED)
            current_state_kood = details['CNV_seisund_kood']
            artefact_kood = self.cnv_seisundid.get('artefakt')
            is_artefact = artefact_kood is not None and current_state_kood == artefact_kood
            self.update_button.config(state=tk.DISABLED if is_artefact else tk.NORMAL)
            self.set_artefact_button.config(state=tk.DISABLED if is_artefact else tk.NORMAL)
            self.set_active_button.config(state=tk.NORMAL if is_artefact else tk.DISABLED)

        except (IndexError, ValueError, KeyError, TypeError) as e:
            messagebox.showerror("Valiku viga", f"Viga valimisel: {e}")
            traceback.print_exc()
            self.clear_form()


    def add_cnv_gui(self):
        # ... (keep logic as before) ...
        """Adds a new CNV via the GUI."""
        if not self.cursor or not self.conn: messagebox.showerror("Viga", "Ühendust andmebaasiga ei õnnestunud luua."); return
        # --- Read Data ---
        dna_kood = self.dna_kood_entry.get().strip(); krom_nimi = self.kromosoom_combo.get()
        koop_display_nimi = self.koopiaarv_combo.get(); tahendus_nimi = self.tahendus_combo.get()
        paritolu_nimi = self.paritolu_combo.get(); algus_str = self.algus_entry.get().strip()
        lopp_str = self.lopp_entry.get().strip()
        # --- Validate ---
        if not all([dna_kood, krom_nimi, koop_display_nimi, tahendus_nimi, paritolu_nimi, algus_str, lopp_str]):
            messagebox.showwarning("Puuduv sisend", "Palun täida kõik väljad"); return
        try:
            algus = int(algus_str); lopp = int(lopp_str)
            if algus <= 0 or lopp <= 0 or algus >= lopp: raise ValueError("Coordinates must be positive integers and start < end.")
        except ValueError as e: messagebox.showwarning("Vale sisend", f"Viga koordinaatides: {e}"); return
        analysis_details = db.get_analysis_details_by_dna(self.cursor, dna_kood)
        if not analysis_details: messagebox.showwarning("Viga", f"Analüüsi koodiga '{dna_kood}' ei õnnestunud leida."); return
        analyys_id = analysis_details['analyys_id']
        krom_kood = self.kromosoomid.get(krom_nimi); koop_kood = self.koopiaarvud.get(koop_display_nimi)
        tahendus_kood = self.tahendused.get(tahendus_nimi); paritolu_kood = self.paritolud.get(paritolu_nimi)
        if not all([krom_kood, koop_kood, tahendus_kood, paritolu_kood]):
             missing = [f"'{n}'" for n, k in [(krom_nimi, krom_kood), (koop_display_nimi, koop_kood), (tahendus_nimi, tahendus_kood), (paritolu_nimi, paritolu_kood)] if k is None]
             messagebox.showerror("Sisemine viga", f"Ei õnnestunud koode leida: {', '.join(missing)}"); return
        # --- Add ---
        print(f"Attempting to add CNV for analysis {analyys_id}...")
        new_cnv_id = db.add_cnv(self.cursor, self.conn, analyys_id, krom_kood, algus, lopp, koop_kood, tahendus_kood, paritolu_kood)
        # --- Feedback & Refresh ---
        if new_cnv_id:
            messagebox.showinfo("CNV lisatud", f"CNV (ID: {new_cnv_id}) edukalt lisatud.")
            self.clear_form(); self.populate_cnv_list(view_type='active') # Show active list after add
        else: messagebox.showerror("Andmebaasi viga", "Ei õnnestunud CNVd lisada. Kontrolli konsooli.")


    def update_cnv_gui(self):
        # ... (keep logic as before) ...
         """Updates the selected CNV."""
         if not self.cursor or not self.conn: messagebox.showerror("Viga", "Andmebaasi ühendus puudub."); return
         if self.selected_cnv_id is None: messagebox.showwarning("Valik puudub", "Palun vali mõni CNV."); return
         # --- Read ---
         krom_nimi = self.kromosoom_combo.get(); koop_display_nimi = self.koopiaarv_combo.get()
         tahendus_nimi = self.tahendus_combo.get(); paritolu_nimi = self.paritolu_combo.get()
         algus_str = self.algus_entry.get().strip(); lopp_str = self.lopp_entry.get().strip()
         # --- Validate ---
         if not all([krom_nimi, koop_display_nimi, tahendus_nimi, paritolu_nimi, algus_str, lopp_str]):
             messagebox.showwarning("Sisend puudu", "Täida kõik kohustuslikud väljad!"); return
         try:
             algus = int(algus_str); lopp = int(lopp_str)
             if algus <= 0 or lopp <= 0 or algus >= lopp: raise ValueError("Coordinates must be positive and start < end.")
         except ValueError as e: messagebox.showwarning("Vale sisend", f"Viga koordinaatides: {e}"); return
         krom_kood = self.kromosoomid.get(krom_nimi); koop_kood = self.koopiaarvud.get(koop_display_nimi)
         tahendus_kood = self.tahendused.get(tahendus_nimi); paritolu_kood = self.paritolud.get(paritolu_nimi)
         if not all([krom_kood, koop_kood, tahendus_kood, paritolu_kood]): messagebox.showerror("Sisemine viga", "Ei õnnestunud leida kõiki klassifikaatorite koode."); return
         # --- Update ---
         print(f"Attempting to update CNV ID: {self.selected_cnv_id}...")
         success = db.update_cnv(self.cursor, self.conn, self.selected_cnv_id, krom_kood, algus, lopp, koop_kood, tahendus_kood, paritolu_kood)
         # --- Feedback & Refresh ---
         if success:
             messagebox.showinfo("CNV muudetud", f"CNV (ID: {self.selected_cnv_id}) edukalt muudetud.")
             self.clear_form(); self.populate_cnv_list(view_type='active') # Refresh active list
         else: messagebox.showerror("Andmebaasi viga", "Ei õnnestunud CNVd muuta (vaata konsooli).")


    def set_cnv_state_gui(self, target_state_name):
         # ... (keep logic as before) ...
         """General function to change CNV state."""
         if not self.cursor or not self.conn: messagebox.showerror("Viga", "Andmebaasi ühendus puudub."); return
         if self.selected_cnv_id is None: messagebox.showwarning("Valik puudu", "Palun vali mõni CNV."); return
         target_state_kood = self.cnv_seisundid.get(target_state_name)
         if target_state_kood is None: messagebox.showerror("Sisemine viga", f"Seisundit '{target_state_name}' ei õnnestunud leida."); return
         # --- Check analysis state if activating ---
         if target_state_name == 'aktiivne':
             cnv_details = db.get_cnv_details_for_edit(self.cursor, self.selected_cnv_id)
             if not cnv_details: messagebox.showerror("Viga", "CNV andmeid seisundi kontrolliks ei õnnestunud laadida."); return
             analyys_id = cnv_details['analyys_id']
             analyys_seisund_nimi = db.get_analyys_seisund_nimi(self.cursor, analyys_id)
             if analyys_seisund_nimi is None: messagebox.showerror("Viga", f"Ei õnnestunud leida seisundi infot sellel analüüsil (ID: {analyys_id})."); return
             if analyys_seisund_nimi == 'artefakt': # Ensure 'artefakt' matches DB value
                  messagebox.showerror("Muutmine keelatud", f"Ei saa CNVd aktiivseks muuta: seotud analüüs (ID: {analyys_id}) on seisundis 'artefakt'."); return
         # --- Change state ---
         print(f"Attempting to set CNV ID {self.selected_cnv_id} state to '{target_state_name}' (kood: {target_state_kood})...")
         success = db.update_cnv_state(self.cursor, self.conn, self.selected_cnv_id, target_state_kood)
         # --- Feedback & Refresh ---
         if success:
              messagebox.showinfo("Õnnestus", f"CNV (ID: {self.selected_cnv_id}) uus seisund: {target_state_name}.")
              self.clear_form(); self.populate_cnv_list(view_type='active') # Refresh active list
         else: messagebox.showerror("Andmebaasi viga", f"Ei õnnestunud muuta CNV seisundit kujule {target_state_name} (vaata veateadet konsoolis).")

    def set_cnv_state_gui_artefact(self): self.set_cnv_state_gui('artefakt')
    def set_cnv_state_gui_active(self): self.set_cnv_state_gui('aktiivne')

    def export_active_cnvs(self):
        """Exports active CNVs to a BED format file."""
        if not self.cursor:
            messagebox.showerror("Viga", "Andmebaasi ühendus puudub.")
            return

        active_cnvs = db.get_active_cnvs_display(self.cursor)
        if not active_cnvs:
            messagebox.showinfo("Andmed puudu", "Ei leidnud aktiivseid CNVsid eksportimiseks.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".bed",
            filetypes=[("BED files", "*.bed"), ("All files", "*.*")],
            title="Save Active CNVs as..."
        )

        if not filepath: return  # User cancelled

        print(f"Exporting {len(active_cnvs)} CNVs to {filepath}...")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # --- Write BED Track Header ---
                track_header = 'track db="hg38" name="GenK_aktiivsed_CNVd" description="Geneetikakeskuse aktiivsed CNV-d (GRCh38)" itemRgb="On"\n'
                f.write(track_header)
                # --- End Header ---

                count = 0
                for cnv in active_cnvs:  # cnv is a sqlite3.Row object
                    row_keys = cnv.keys()
                    try:
                        # --- Get data using dictionary-style access [] ---
                        chrom_raw = cnv['kromosoom_nimi'] if 'kromosoom_nimi' in row_keys else ''
                        chrom = f"chr{chrom_raw}" if chrom_raw else "chrNA"

                        try:
                            start_1based = int(cnv['alguskoordinaat'])
                        except (ValueError, TypeError, KeyError):
                            start_1based = 1
                        try:
                            end_1based = int(cnv['loppkoordinaat'])
                        except (ValueError, TypeError, KeyError):
                            end_1based = 1

                        # BED format: 0-based start, exclusive end
                        start_0based = max(0, start_1based - 1)
                        end_exclusive = end_1based

                        # Create name field: Example uses DNA_kood - adjust if needed
                        dna_kood = cnv['DNA_kood'] if 'DNA_kood' in row_keys else 'NA'
                        name = f"{dna_kood}"

                        score = '0'  # Standard BED score, often 0 or 1000
                        strand = '.'  # CNVs usually don't have strand info

                        # Get RGB color
                        rgb_color = cnv['RGB_varv'] if 'RGB_varv' in row_keys else '0,0,0'
                        # Ensure it's in the correct comma-separated format
                        if not isinstance(rgb_color, str) or rgb_color.count(',') != 2:
                            rgb_color = '0,0,0'  # Default to black if format is wrong

                        # thickStart and thickEnd are often the same as start/end for simple BED
                        thick_start = start_0based
                        thick_end = end_exclusive

                        # --- Write formatted BED line ---
                        bed_line = f"{chrom}\t{start_0based}\t{end_exclusive}\t{name}\t{score}\t{strand}\t{thick_start}\t{thick_end}\t{rgb_color}\n"
                        f.write(bed_line)
                        count += 1
                    except KeyError as ke:
                        current_id = cnv['cnv_id'] if 'cnv_id' in row_keys else 'UNKNOWN'
                        print(f"KeyError processing CNV row for export (ID: {current_id}): Missing key {ke}")
                        messagebox.showwarning("Rea võtme viga",
                                               f"Viga CNV ID {current_id} ekspordil: andmed puudu {ke}. Katkestatud.")
                    except Exception as item_e:
                        current_id = cnv['cnv_id'] if 'cnv_id' in row_keys else 'UNKNOWN'
                        print(f"Error processing CNV row for export (ID: {current_id}): {item_e}")
                        messagebox.showwarning("Rea viga",
                                               f"Viga CNV-ga millel on ID {current_id} eksportimisel: {item_e}. Katkestatud.")

            messagebox.showinfo("Eksport edukas", f"{count} aktiivset CNVd eksporditud siia:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Ekspordi viga", f"Tekkis viga faili kirjutamisel: {e}")
            print(f"Error during BED export: {e}")


    def on_closing(self):
        """Cleanup on application close."""
        print("Closing application...")
        if messagebox.askokcancel("Välju", "Kas soovite kindlasti väljuda?"):
             if self.conn:
                 db.db_disconnect(self.conn) # Use disconnect function
             if not cnv_backup.backup_if_due():
                 messagebox.showwarning("Varukoopia", f"Varukoopiat ei õnnestunud teha kausta {cnv_backup.BACKUP_DIR}.")
             self.root.destroy()


# --- Main Application Setup ---
if __name__ == "__main__":
    main_root = tk.Tk()
    app = CNVAdminApp(main_root)
    main_root.mainloop()