""""
Run SQLite database GUI for CNV Register administration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import traceback # For detailed error logging
from datetime import date
import cnv_registry_db as db # Import the data access layer module
import cnv_backup

class CNVAdminApp:
    # Estonian column headings shown in the CNV list (keys are DB column names)
    COLUMN_HEADINGS = {
        "cnv_id": "ID", "dna_code": "DNA kood", "chromosome_name": "Kromosoom",
        "start_pos": "Algus", "end_pos": "Lõpp", "copy_number_value": "Koopiaarv",
        "interpretation_name": "Tähendus", "inheritance_name": "Päritolu",
        "cnv_status_name": "Seisund",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("CNV register - Administraatori vaade (sisse logitud)")
        self.root.geometry("950x650")

        # --- Database Connection ---
        self.conn = None
        self.cursor = None
        self.connect_to_database() # Initialize connection and cursor

        # --- Load Classifiers (Data for Comboboxes etc.) ---
        self.chromosomes = {}
        self.copy_numbers = {}
        self.interpretations = {}
        self.inheritances = {}
        self.cnv_statuses = {}
        self.chromosomes_rev = {}
        self.copy_numbers_rev = {}
        self.interpretations_rev = {}
        self.inheritances_rev = {}
        self.cnv_statuses_rev = {}

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
        """Attempts to connect to the database using the function from cnv_registry_db."""
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
            # chromosome
            chrom_data = db.get_active_classifications(self.cursor, 'chromosome', 'chromosome_code', 'chromosome_name')
            self.chromosomes = {row['chromosome_name']: row['chromosome_code'] for row in chrom_data}
            self.chromosomes_rev = {v: k for k, v in self.chromosomes.items()}

            # copy_number (needs value and name)
            copy_number_data = db.get_active_classifications(self.cursor, 'copy_number', 'copy_number_code', 'copy_number_name', other_cols=['copy_number_value'])
            self.copy_numbers = {f"{row['copy_number_value']} ({row['copy_number_name']})": row['copy_number_code'] for row in copy_number_data}
            self.copy_numbers_rev = {v: k for k, v in self.copy_numbers.items()}

            # interpretation
            interpretation_data = db.get_active_classifications(self.cursor, 'interpretation', 'interpretation_code', 'interpretation_name')
            self.interpretations = {row['interpretation_name']: row['interpretation_code'] for row in interpretation_data}
            self.interpretations_rev = {v: k for k, v in self.interpretations.items()}

            # inheritance
            inheritance_data = db.get_active_classifications(self.cursor, 'inheritance', 'inheritance_code', 'inheritance_name')
            self.inheritances = {row['inheritance_name']: row['inheritance_code'] for row in inheritance_data}
            self.inheritances_rev = {v: k for k, v in self.inheritances.items()}

            # cnv_status (Fetch all states, including inactive like 'artefakt')
            try:
                self.cursor.execute("SELECT cnv_status_code, cnv_status_name FROM cnv_status ORDER BY cnv_status_name;")
                all_status_data = self.cursor.fetchall()
                self.cnv_statuses = {row['cnv_status_name']: row['cnv_status_code'] for row in all_status_data}
                self.cnv_statuses_rev = {v: k for k, v in self.cnv_statuses.items()}
            except sqlite3.Error as e:
                 print(f"ERROR fetching all cnv_status: {e}")
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
        self.dna_code_entry = ttk.Entry(form_frame, width=15)
        self.dna_code_entry.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)
        ttk.Label(form_frame, text="Kromosoom:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.chromosome_combo = ttk.Combobox(form_frame,
                                            values=sorted(list(self.chromosomes.keys()), key=lambda x: int(x) if x.isdigit() else ord(x[0])),
                                            width=5, state="readonly")
        self.chromosome_combo.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 1
        ttk.Label(form_frame, text="Alguskoordinaat:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        self.start_entry = ttk.Entry(form_frame, width=15)
        self.start_entry.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)
        ttk.Label(form_frame, text="Lõppkoordinaat:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.end_entry = ttk.Entry(form_frame, width=15)
        self.end_entry.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 2
        ttk.Label(form_frame, text="Koopiaarv:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        copy_number_sorted_keys = sorted(self.copy_numbers.keys(), key=lambda x: int(x.split()[0]))
        self.copy_number_combo = ttk.Combobox(form_frame, values=copy_number_sorted_keys, width=20, state="readonly")
        self.copy_number_combo.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W) # Removed columnspan
        ttk.Label(form_frame, text="Tähendus:").grid(row=row_num, column=2, padx=(10,2), pady=2, sticky=tk.W)
        self.interpretation_combo = ttk.Combobox(form_frame, values=sorted(list(self.interpretations.keys())), width=15, state="readonly")
        self.interpretation_combo.grid(row=row_num, column=3, padx=2, pady=2, sticky=tk.W)
        row_num += 1
        # Row 3
        ttk.Label(form_frame, text="Päritolu:").grid(row=row_num, column=0, padx=(0,2), pady=2, sticky=tk.W)
        self.inheritance_combo = ttk.Combobox(form_frame, values=sorted(list(self.inheritances.keys())), width=15, state="readonly")
        self.inheritance_combo.grid(row=row_num, column=1, padx=2, pady=2, sticky=tk.W)

        # --- Action Buttons Frame ---
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(side=tk.RIGHT, padx=5, pady=5, anchor=tk.N) # Anchor North

        self.add_button = ttk.Button(button_frame, text="Lisa CNV", command=self.add_cnv_gui)
        self.add_button.pack(fill=tk.X, pady=2)
        # Changed button text
        self.update_button = ttk.Button(button_frame, text="Muuda CNV-d", command=self.update_cnv_gui, state=tk.DISABLED)
        self.update_button.pack(fill=tk.X, pady=2)
        self.set_artefact_button = ttk.Button(button_frame, text="Märgi artefaktiks", command=self.set_cnv_state_gui_artefact, state=tk.DISABLED)
        self.set_artefact_button.pack(fill=tk.X, pady=2)
        self.set_active_button = ttk.Button(button_frame, text="Märgi aktiivseks", command=self.set_cnv_state_gui_active, state=tk.DISABLED)
        self.set_active_button.pack(fill=tk.X, pady=2)
        self.clear_button = ttk.Button(button_frame, text="Tühjenda vorm", command=self.clear_form)
        self.clear_button.pack(fill=tk.X, pady=2)

        # --- List View (Treeview) ---
        # Define ALL columns using DB names; this tuple is used consistently
        self.all_db_columns = (
            "cnv_id", "dna_code", "chromosome_name", "start_pos",
            "end_pos", "copy_number_value", "interpretation_name",
            "inheritance_name", "cnv_status_name"
        )
        # Create Treeview inside self.list_frame
        self.cnv_tree = ttk.Treeview(self.list_frame, columns=self.all_db_columns, show="headings")

        # Configure ALL headings and columns, bind click for sorting
        for col_id in self.all_db_columns:
            # Bind heading click to sorting function
            self.cnv_tree.heading(col_id, text=self.COLUMN_HEADINGS.get(col_id, col_id),
                                  command=lambda c=col_id: self.sort_treeview_column(c))
            # Set widths, anchor, and stretch properties
            if col_id == "cnv_id": width = 0; anchor = tk.W; stretch = tk.NO # Hide cnv_id
            elif col_id == "dna_code": width = 90; anchor = tk.W; stretch = tk.YES
            elif col_id == "chromosome_name": width = 50; anchor = tk.CENTER; stretch = tk.YES
            elif col_id == "start_pos": width = 100; anchor = tk.E; stretch = tk.YES
            elif col_id == "end_pos": width = 100; anchor = tk.E; stretch = tk.YES
            elif col_id == "copy_number_value": width = 60; anchor = tk.CENTER; stretch = tk.YES
            elif col_id == "interpretation_name": width = 120; anchor = tk.W; stretch = tk.YES
            elif col_id == "inheritance_name": width = 100; anchor = tk.W; stretch = tk.YES
            elif col_id == "cnv_status_name": width = 80; anchor = tk.W; stretch = tk.YES
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
        ttk.Button(list_control_frame, text="Kuva analüüsi CNV-d", command=self.populate_cnv_list_by_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_control_frame, text="Kuva kõik aktiivsed", command=lambda: self.populate_cnv_list(view_type='active')).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_control_frame, text="Ekspordi aktiivsed (BED)", command=self.export_active_cnvs).pack(side=tk.LEFT, padx=5)


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
            numeric_cols = ['cnv_id', 'start_pos', 'end_pos', 'copy_number_value']
            chr_cols = ['chromosome_name']

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
        self.dna_code_entry.config(state=tk.NORMAL) # Enable before clearing
        self.dna_code_entry.delete(0, tk.END)
        self.start_entry.delete(0, tk.END)
        self.end_entry.delete(0, tk.END)
        self.chromosome_combo.set('')
        self.copy_number_combo.set('')
        self.interpretation_combo.set('')
        self.inheritance_combo.set('')
        # Reset DNA entry state based on whether a selection is active (it's not after clear)
        # self.dna_code_entry.config(state=tk.NORMAL) # Keep enabled for adding

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
                "dna_code", "chromosome_name", "start_pos", "end_pos",
                "copy_number_value", "interpretation_name", "inheritance_name", "cnv_status_name"
            ) # Exclude cnv_id from visible
            # Reset list frame title
            self.list_frame.config(text="Aktiivsete CNV-de nimekiri") # More descriptive title
            if cnvs is None:
                cnvs = db.get_active_cnvs_display(self.cursor) # Fetches state too
        elif view_type == 'single_analysis':
            # Columns to display for the "Single Analysis" view (hide dna_code)
            display_columns_subset = (
                "chromosome_name", "start_pos", "end_pos", "copy_number_value",
                "interpretation_name", "inheritance_name", "cnv_status_name"
            ) # Exclude cnv_id and dna_code from visible
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
        dna_code = self.view_dna_entry.get().strip()
        if not dna_code: messagebox.showwarning("Sisend puudu", "Otsimiseks sisesta analüüsi kood."); return

        analysis_details = db.get_analysis_details_by_dna(self.cursor, dna_code)
        if not analysis_details:
            messagebox.showinfo("Viga", f"Analüüsi koodiga '{dna_code}' ei leitud.")
            self.list_frame.config(text="CNV nimekiri") # Reset title
            self.populate_cnv_list([], view_type='single_analysis')
            return

        analysis_id = analysis_details['analysis_id']
        print(f"Fetching CNVs for analysis ID: {analysis_id} (DNA: {dna_code})")
        cnvs = db.get_cnvs_for_analysis_display(self.cursor, analysis_id)
        # Update list frame title BEFORE populating
        self.list_frame.config(text=f"{dna_code} CNV nimekiri")
        # Call populate_cnv_list, passing data and view type
        self.populate_cnv_list(cnvs, view_type='single_analysis')
        if not cnvs: messagebox.showinfo("Tulemusteta", f"Ei õnnestunud leida ühtegi CNV-d DNA koodiga '{dna_code}'.")


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
            self.dna_code_entry.config(state=tk.NORMAL)
            self.dna_code_entry.delete(0, tk.END)
            self.dna_code_entry.insert(0, details['dna_code'])
            self.dna_code_entry.config(state=tk.DISABLED)
            self.start_entry.delete(0, tk.END); self.start_entry.insert(0, details['start_pos'])
            self.end_entry.delete(0, tk.END); self.end_entry.insert(0, details['end_pos'])
            self.chromosome_combo.set(self.chromosomes_rev.get(details['chromosome_code'], ''))
            self.copy_number_combo.set(self.copy_numbers_rev.get(details['copy_number_code'], ''))
            self.interpretation_combo.set(self.interpretations_rev.get(details['interpretation_code'], ''))
            self.inheritance_combo.set(self.inheritances_rev.get(details['inheritance_code'], ''))

            # Update button states
            self.add_button.config(state=tk.DISABLED)
            current_state_code = details['cnv_status_code']
            artefact_code = self.cnv_statuses.get('artefakt')
            is_artefact = artefact_code is not None and current_state_code == artefact_code
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
        dna_code = self.dna_code_entry.get().strip(); chrom_name = self.chromosome_combo.get()
        copy_number_display_name = self.copy_number_combo.get(); interpretation_name = self.interpretation_combo.get()
        inheritance_name = self.inheritance_combo.get(); start_str = self.start_entry.get().strip()
        end_str = self.end_entry.get().strip()
        # --- Validate ---
        if not all([dna_code, chrom_name, copy_number_display_name, interpretation_name, inheritance_name, start_str, end_str]):
            messagebox.showwarning("Puuduv sisend", "Palun täida kõik väljad"); return
        try:
            start = int(start_str); end = int(end_str)
            if start <= 0 or end <= 0 or start >= end: raise ValueError("Coordinates must be positive integers and start < end.")
        except ValueError as e: messagebox.showwarning("Vale sisend", f"Viga koordinaatides: {e}"); return
        analysis_details = db.get_analysis_details_by_dna(self.cursor, dna_code)
        if not analysis_details: messagebox.showwarning("Viga", f"Analüüsi koodiga '{dna_code}' ei õnnestunud leida."); return
        analysis_id = analysis_details['analysis_id']
        chrom_code = self.chromosomes.get(chrom_name); copy_number_code = self.copy_numbers.get(copy_number_display_name)
        interpretation_code = self.interpretations.get(interpretation_name); inheritance_code = self.inheritances.get(inheritance_name)
        if not all([chrom_code, copy_number_code, interpretation_code, inheritance_code]):
             missing = [f"'{n}'" for n, k in [(chrom_name, chrom_code), (copy_number_display_name, copy_number_code), (interpretation_name, interpretation_code), (inheritance_name, inheritance_code)] if k is None]
             messagebox.showerror("Sisemine viga", f"Ei õnnestunud koode leida: {', '.join(missing)}"); return
        # --- Add ---
        print(f"Attempting to add CNV for analysis {analysis_id}...")
        new_cnv_id = db.add_cnv(self.cursor, self.conn, analysis_id, chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code)
        # --- Feedback & Refresh ---
        if new_cnv_id:
            messagebox.showinfo("CNV lisatud", f"CNV (ID: {new_cnv_id}) edukalt lisatud.")
            self.clear_form(); self.populate_cnv_list(view_type='active') # Show active list after add
        else: messagebox.showerror("Andmebaasi viga", "Ei õnnestunud CNV-d lisada. Kontrolli konsooli.")


    def update_cnv_gui(self):
        # ... (keep logic as before) ...
         """Updates the selected CNV."""
         if not self.cursor or not self.conn: messagebox.showerror("Viga", "Andmebaasi ühendus puudub."); return
         if self.selected_cnv_id is None: messagebox.showwarning("Valik puudub", "Palun vali mõni CNV."); return
         # --- Read ---
         chrom_name = self.chromosome_combo.get(); copy_number_display_name = self.copy_number_combo.get()
         interpretation_name = self.interpretation_combo.get(); inheritance_name = self.inheritance_combo.get()
         start_str = self.start_entry.get().strip(); end_str = self.end_entry.get().strip()
         # --- Validate ---
         if not all([chrom_name, copy_number_display_name, interpretation_name, inheritance_name, start_str, end_str]):
             messagebox.showwarning("Sisend puudu", "Täida kõik kohustuslikud väljad!"); return
         try:
             start = int(start_str); end = int(end_str)
             if start <= 0 or end <= 0 or start >= end: raise ValueError("Coordinates must be positive and start < end.")
         except ValueError as e: messagebox.showwarning("Vale sisend", f"Viga koordinaatides: {e}"); return
         chrom_code = self.chromosomes.get(chrom_name); copy_number_code = self.copy_numbers.get(copy_number_display_name)
         interpretation_code = self.interpretations.get(interpretation_name); inheritance_code = self.inheritances.get(inheritance_name)
         if not all([chrom_code, copy_number_code, interpretation_code, inheritance_code]): messagebox.showerror("Sisemine viga", "Ei õnnestunud leida kõiki klassifikaatorite koode."); return
         # --- Update ---
         print(f"Attempting to update CNV ID: {self.selected_cnv_id}...")
         success = db.update_cnv(self.cursor, self.conn, self.selected_cnv_id, chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code)
         # --- Feedback & Refresh ---
         if success:
             messagebox.showinfo("CNV muudetud", f"CNV (ID: {self.selected_cnv_id}) edukalt muudetud.")
             self.clear_form(); self.populate_cnv_list(view_type='active') # Refresh active list
         else: messagebox.showerror("Andmebaasi viga", "Ei õnnestunud CNV-d muuta (vaata konsooli).")


    def set_cnv_state_gui(self, target_state_name):
         # ... (keep logic as before) ...
         """General function to change CNV state."""
         if not self.cursor or not self.conn: messagebox.showerror("Viga", "Andmebaasi ühendus puudub."); return
         if self.selected_cnv_id is None: messagebox.showwarning("Valik puudu", "Palun vali mõni CNV."); return
         target_state_code = self.cnv_statuses.get(target_state_name)
         if target_state_code is None: messagebox.showerror("Sisemine viga", f"Seisundit '{target_state_name}' ei õnnestunud leida."); return
         # --- Check analysis state if activating ---
         if target_state_name == 'aktiivne':
             cnv_details = db.get_cnv_details_for_edit(self.cursor, self.selected_cnv_id)
             if not cnv_details: messagebox.showerror("Viga", "CNV andmeid seisundi kontrolliks ei õnnestunud laadida."); return
             analysis_id = cnv_details['analysis_id']
             analysis_status_name = db.get_analysis_status_name(self.cursor, analysis_id)
             if analysis_status_name is None: messagebox.showerror("Viga", f"Ei õnnestunud leida seisundi infot sellel analüüsil (ID: {analysis_id})."); return
             if analysis_status_name == 'artefakt': # Ensure 'artefakt' matches DB value
                  messagebox.showerror("Muutmine keelatud", f"Ei saa CNV-d aktiivseks muuta: seotud analüüs (ID: {analysis_id}) on seisundis 'artefakt'."); return
         # --- Change state ---
         print(f"Attempting to set CNV ID {self.selected_cnv_id} state to '{target_state_name}' (kood: {target_state_code})...")
         success = db.update_cnv_state(self.cursor, self.conn, self.selected_cnv_id, target_state_code)
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
            messagebox.showinfo("Andmed puudu", "Ei leidnud aktiivseid CNV-sid eksportimiseks.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".bed",
            filetypes=[("BED files", "*.bed"), ("All files", "*.*")],
            title="Salvesta aktiivsed CNV-d…"
        )

        if not filepath: return  # User cancelled

        print(f"Exporting {len(active_cnvs)} CNVs to {filepath}...")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # --- Write BED Track Header ---
                export_date = date.today().isoformat()
                track_header = f'track db="hg38" name="cnv_registry_active" description="Active CNVs from local CNV registry, exported {export_date} (GRCh38)" itemRgb="On"\n'
                f.write(track_header)
                # --- End Header ---

                count = 0
                for cnv in active_cnvs:  # cnv is a sqlite3.Row object
                    row_keys = cnv.keys()
                    try:
                        # --- Get data using dictionary-style access [] ---
                        chrom_raw = cnv['chromosome_name'] if 'chromosome_name' in row_keys else ''
                        chrom = f"chr{chrom_raw}" if chrom_raw else "chrNA"

                        try:
                            start_1based = int(cnv['start_pos'])
                        except (ValueError, TypeError, KeyError):
                            start_1based = 1
                        try:
                            end_1based = int(cnv['end_pos'])
                        except (ValueError, TypeError, KeyError):
                            end_1based = 1

                        # BED format: 0-based start, exclusive end
                        start_0based = max(0, start_1based - 1)
                        end_exclusive = end_1based

                        # Create name field: Example uses dna_code - adjust if needed
                        dna_code = cnv['dna_code'] if 'dna_code' in row_keys else 'NA'
                        name = f"{dna_code}"

                        score = '0'  # Standard BED score, often 0 or 1000
                        strand = '.'  # CNVs usually don't have strand info

                        # Get RGB color
                        rgb_color = cnv['rgb_color'] if 'rgb_color' in row_keys else '0,0,0'
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

            messagebox.showinfo("Eksport edukas", f"{count} aktiivset CNV-d eksporditud siia:\n{filepath}")

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