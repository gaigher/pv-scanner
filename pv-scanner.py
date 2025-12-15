#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import csv
import json
from datetime import datetime
from typing import Optional, Dict, Tuple

import platform
if platform.system() == "Windows":
    import winsound
else:
    winsound = None

from PyQt6 import QtWidgets, QtCore, QtGui  # pyright: ignore



# Fichier pour sauvegarder les patterns de parsing manuel
PATTERNS_FILE = "patterns_parse.json"

def charger_patterns() -> Dict[str, Dict]:
    """
    Charge les patterns de parsing manuel depuis le fichier JSON.
    Retourne un dictionnaire vide si le fichier n'existe pas ou est invalide.
    """
    if not os.path.exists(PATTERNS_FILE):
        return {}
    try:
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def sauvegarder_patterns(patterns: Dict[str, Dict]):
    """
    Sauvegarde les patterns de parsing manuel dans le fichier JSON.
    """
    try:
        with open(PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def appliquer_pattern(code: str, pattern: Dict) -> Optional[str]:
    """
    Applique un pattern sauvegardé à un code-barres.
    Retourne le poids formaté ou None si le pattern ne correspond pas.
    """
    pos_debut = pattern.get('pos_debut', 0)
    pos_decimal = pattern.get('pos_decimal', -1)
    longueur = pattern.get('longueur', 0)
    
    # Vérifier si le code correspond au pattern (longueur ou préfixe)
    if 'longueur_code' in pattern:
        if len(code) != pattern['longueur_code']:
            return None
    if 'prefixe' in pattern:
        if not code.startswith(pattern['prefixe']):
            return None
    
    # Extraire le poids
    if longueur > 0:
        poids_brut = code[pos_debut:pos_debut + longueur]
    else:
        poids_brut = code[pos_debut:]
    
    # Formater avec la décimale
    if pos_decimal >= 0 and pos_decimal < len(poids_brut):
        partie_entiere = poids_brut[:pos_decimal]
        partie_decimale = poids_brut[pos_decimal:]
        poids_formate = partie_entiere + "," + partie_decimale
        try:
            partie_entiere_int = str(int(partie_entiere)) if partie_entiere else "0"
            poids_formate = partie_entiere_int + "," + partie_decimale
        except ValueError:
            pass
    else:
        poids_formate = poids_brut
        try:
            poids_formate = str(int(poids_brut))
        except ValueError:
            pass
    
    return poids_formate

def parser_code_gs1(chaine: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse un code GS1 et retourne (poids_ia, poids_valeur, date_valeur).
    
    Retourne:
        - poids_ia: L'IA du poids trouvé (ex: "3103") ou None
        - poids_valeur: La valeur brute du poids (6 chiffres) ou None
        - date_valeur: La valeur brute de la DLC (6 chiffres AAMMJJ) ou None
    """
    if chaine is None or len(chaine) < 2:
        return None, None, None
    
    # Définition des IA avec longueur fixe de données (selon norme GS1)
    # On inclut les IA standards même si on ne les utilise pas, pour pouvoir les sauter
    ia_longueurs = {
        '00': 18,   # SSCC (Serial Shipping Container Code)
        '01': 14,   # GTIN
        '02': 14,   # GTIN of Contained Trade Items
        '11': 6,    # Date de production (AAMMJJ)
        '12': 6,    # Due Date (AAMMJJ)
        '13': 6,    # Packaging Date (AAMMJJ)
        '15': 6,    # Date limite de consommation (AAMMJJ)
        '16': 6,    # Sell By Date (AAMMJJ)
        '17': 6,    # Date d'expiration (AAMMJJ)
        '3100': 6,  # Poids net (kg) - 0 décimale
        '3101': 6,  # Poids net (kg) - 1 décimale
        '3102': 6,  # Poids net (kg) - 2 décimales
        '3103': 6,  # Poids net (kg) - 3 décimales
        '3104': 6,  # Poids net (kg) - 4 décimales
        '3105': 6,  # Poids net (kg) - 5 décimales
        '3200': 6,  # Poids net (livres) - 0 décimale
        '3201': 6,  # Poids net (livres) - 1 décimale
        '3202': 6,  # Poids net (livres) - 2 décimales
        '3203': 6,  # Poids net (livres) - 3 décimales
        '3204': 6,  # Poids net (livres) - 4 décimales
        '3205': 6,  # Poids net (livres) - 5 décimales
        '3300': 6,  # Poids logistique (kg) - 0 décimale
        '3301': 6,  # Poids logistique (kg) - 1 décimale
        '3302': 6,  # Poids logistique (kg) - 2 décimales
        '3303': 6,  # Poids logistique (kg) - 3 décimales
        '3304': 6,  # Poids logistique (kg) - 4 décimales
        '3305': 6,  # Poids logistique (kg) - 5 décimales
    }
    
    # IA à longueur variable (nécessitent un séparateur FNC1 ou détection du prochain IA)
    ia_longueur_variable = {'10', '21', '22'}  # 10: Numéro de lot, 21: Numéro de série, 22: Consumer Product Variant
    
    # Parsing séquentiel depuis le début (conforme norme GS1)
    pos = 0
    poids_ia = None
    poids_valeur = None
    date_valeur = None
    
    while pos < len(chaine):
        ia_trouve = False
        
        # Chercher d'abord les IA de 2 chiffres
        if pos + 2 <= len(chaine):
            ia_2 = chaine[pos:pos+2]
            if ia_2 in ia_longueurs:
                longueur = ia_longueurs[ia_2]
                if pos + 2 + longueur <= len(chaine):
                    valeur = chaine[pos+2:pos+2+longueur]
                    # Si c'est l'IA (15) pour la DLC, on le stocke
                    if ia_2 == '15':
                        date_valeur = valeur
                    # IA trouvé : on saute l'IA (2) + ses données (longueur)
                    pos += 2 + longueur
                    ia_trouve = True
                    continue
            elif ia_2 in ia_longueur_variable:
                # IA à longueur variable (ex: IA 10 = numéro de lot)
                pos_donnees = pos + 2
                pos_prochain_ia = None
                
                # Chercher le prochain IA connu en avançant caractère par caractère
                for i in range(pos_donnees, min(pos_donnees + 20, len(chaine))):
                    if i + 2 <= len(chaine):
                        ia_test_2 = chaine[i:i+2]
                        if ia_test_2 in ia_longueurs:
                            pos_prochain_ia = i
                            break
                    if i + 4 <= len(chaine):
                        ia_test_4 = chaine[i:i+4]
                        if ia_test_4 in ia_longueurs:
                            pos_prochain_ia = i
                            break
                
                if pos_prochain_ia is not None:
                    pos = pos_prochain_ia
                    ia_trouve = True
                    continue
                else:
                    break
        
        # Chercher les IA de 4 chiffres
        if not ia_trouve and pos + 4 <= len(chaine):
            ia_4 = chaine[pos:pos+4]
            if ia_4 in ia_longueurs:
                longueur = ia_longueurs[ia_4]
                if pos + 4 + longueur <= len(chaine):
                    valeur = chaine[pos+4:pos+4+longueur]
                    # Si c'est un IA de poids (310x, 320x, 330x), on le stocke
                    if ia_4.startswith('310') or ia_4.startswith('320') or ia_4.startswith('330'):
                        poids_ia = ia_4
                        poids_valeur = valeur
                    # IA trouvé : on saute l'IA (4) + ses données (longueur)
                    pos += 4 + longueur
                    ia_trouve = True
                    continue
        
        # Si aucun IA reconnu à cette position, chercher le prochain IA connu
        # pour ignorer les IA non reconnus et continuer le parsing
        if not ia_trouve:
            pos_prochain_ia = None
            # Chercher le prochain IA connu en avançant caractère par caractère
            for i in range(pos + 1, min(pos + 30, len(chaine))):  # Chercher jusqu'à 30 caractères
                # Vérifier si on trouve un IA de 2 chiffres connu
                if i + 2 <= len(chaine):
                    ia_test_2 = chaine[i:i+2]
                    if ia_test_2 in ia_longueurs or ia_test_2 in ia_longueur_variable:
                        pos_prochain_ia = i
                        break
                # Vérifier si on trouve un IA de 4 chiffres connu
                if i + 4 <= len(chaine):
                    ia_test_4 = chaine[i:i+4]
                    if ia_test_4 in ia_longueurs:
                        pos_prochain_ia = i
                        break
            
            if pos_prochain_ia is not None:
                # On a trouvé un IA connu, on saute jusqu'à lui
                pos = pos_prochain_ia
                continue
            else:
                # Aucun IA connu trouvé, on arrête
                break
    
    return poids_ia, poids_valeur, date_valeur

def formater_ligne(ligne: str):
    """
    Analyse une ligne brute (code scanné) et renvoie une chaîne formatée
    représentant le poids avec une virgule décimale (ex: "1,234").
    Retourne None si la ligne ne correspond pas à un format connu.
    
    Règles :
    - Si la chaîne fait 13 caractères (EAN-13) : extrait positions 7–11 (5 caractères) et rend "xx,xxx".
    - Sinon, parse dynamiquement les IA GS1 en recherchant séquentiellement :
      * IA 01 : GTIN (14 chiffres)
      * IA 310x : Poids net en kg (6 chiffres, x = nombre de décimales)
      * IA 15 : DLC (6 chiffres)
      * Et autres IA selon la norme GS1
    - Si aucun format reconnu, essayer les patterns sauvegardés.
    """
    if ligne is None:
        return None
    chaine = ligne.strip()
    
    # Format EAN-13 (13 caractères)
    if len(chaine) == 13:
        extrait = chaine[7:12]
        if len(extrait) >= 5:
            return extrait[0:2] + "," + extrait[2:]
        return None
    
    # Format GS1 : utiliser la fonction commune de parsing
    poids_ia, poids_valeur, _ = parser_code_gs1(chaine)
    
    # Si on a trouvé un IA de poids, on le formate
    if poids_ia and poids_valeur:
        if len(poids_valeur) == 6:
            # Le dernier chiffre de l'IA indique le nombre de décimales
            nb_decimales = int(poids_ia[3])
            
            # Extraire la valeur numérique du poids
            if nb_decimales == 0:
                poids_brut = int(poids_valeur)
            else:
                partie_entiere_str = poids_valeur[:6-nb_decimales]
                partie_decimale_str = poids_valeur[6-nb_decimales:]
                poids_brut = float(partie_entiere_str + "." + partie_decimale_str)
            
            # Convertir les livres (320x) en kilogrammes (1 livre = 0.453592 kg)
            if poids_ia.startswith('320'):
                poids_brut = poids_brut * 0.453592
            
            # Pour 330x (poids logistique), on garde tel quel (déjà en kg)
            # Pour 310x (poids net), on garde tel quel (déjà en kg)
            
            # Formater le résultat en kg avec virgule
            poids_kg_str = f"{poids_brut:.6f}".rstrip('0').rstrip('.')
            if '.' in poids_kg_str:
                partie_entiere, partie_decimale = poids_kg_str.split('.')
                # Enlever les zéros non significatifs à gauche de la partie entière
                partie_entiere = str(int(partie_entiere)) if partie_entiere else "0"
                return partie_entiere + "," + partie_decimale
            else:
                return str(int(poids_brut))
    
    # Si aucun format reconnu, essayer les patterns sauvegardés
    patterns = charger_patterns()
    for pattern_key, pattern in patterns.items():
        resultat = appliquer_pattern(chaine, pattern)
        if resultat:
            return resultat
    
    return None


def valeur_formatee_vers_float(valeur: str) -> float:
    """
    Convertit une valeur formatée (avec virgule ou point) en float.
    Si la valeur est invalide ou vide, retourne 0.0.
    """
    if valeur is None:
        return 0.0
    chaine = str(valeur).strip()
    if chaine == "":
        return 0.0
    chaine = chaine.replace(",", ".")
    try:
        return float(chaine)
    except ValueError:
        return 0.0


def extraire_dlc_from_scan(texte: str) -> Optional[str]:
    """
    Extrait la DLC (AI 15) du texte fourni en parsant séquentiellement les IA GS1.
    l'identifiant d'application (15) dans le code-barres GS1.
    Renvoie une chaîne au format 'DD/MM/YYYY' si valide, sinon None.

    Conforme à la norme GS1 pour le parsing des identifiants d'application (IA).
    - Utilise la fonction commune parser_code_gs1 pour extraire l'IA (15).
    - L'IA (15) contient 6 chiffres au format AAMMJJ (Date Limite de Consommation).
    - Interprète AAMMJJ → 20AA-MM-JJ (valide jusqu'en 2099).
    - Si date invalide, retourne None.
    """
    if texte is None:
        return None
    texte_nettoye = texte.strip()
    if len(texte_nettoye) < 8:  # Minimum : "15" + 6 chiffres
        return None
    
    # Utiliser la fonction commune de parsing
    _, _, date_valeur = parser_code_gs1(texte_nettoye)
    
    # Si on a trouvé l'IA (15), on parse la date
    if date_valeur and len(date_valeur) == 6:
        try:
            aa = int(date_valeur[0:2])
            mois = int(date_valeur[2:4])
            jour = int(date_valeur[4:6])
            annee = 2000 + aa  # règle : AA -> 20AA
            date_obj = datetime(annee, mois, jour)  # valider date
            return f"{date_obj.day:02d}/{date_obj.month:02d}/{date_obj.year:04d}"
        except Exception:
            return None
    
    return None


class TablePV(QtWidgets.QTableWidget):
    """
    Collage multi-lignes.
    La table a 2 colonnes : [Poids en kg, DLC].
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def keyPressEvent(self, evenement: QtGui.QKeyEvent) -> None:
        """
        Intercepte Ctrl+V / Cmd+V pour gérer le collage de plusieurs lignes.
        Lors d'un collage multi-lignes : on insère chaque ligne dans la colonne 0
        (Poids) et on tente d'extraire la DLC pour la colonne 1.
        """
        controle = (evenement.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        meta = (evenement.modifiers() & QtCore.Qt.KeyboardModifier.MetaModifier)
        if (controle or meta) and evenement.key() == QtCore.Qt.Key.Key_V:
            presse_papiers = QtWidgets.QApplication.clipboard()
            texte = presse_papiers.text()
            if texte:
                lignes = texte.splitlines()
                if len(lignes) > 1:
                    ligne_depart = self.currentRow()
                    if ligne_depart < 0:
                        ligne_depart = 0
                    necessaires = ligne_depart + len(lignes) - self.rowCount()
                    if necessaires > 0:
                        self.setRowCount(self.rowCount() + necessaires)
                    ligne = ligne_depart
                    # insérer et formater chaque ligne
                    self.blockSignals(True)
                    for texte_lu in lignes:
                        origine = texte_lu
                        # colonne 0 : poids (formaté si possible)
                        formate = formater_ligne(origine)
                        if formate:
                            self.setItem(ligne, 0, QtWidgets.QTableWidgetItem(formate))
                        else:
                            # si non formatable, on laisse le texte brut (permet édition)
                            self.setItem(ligne, 0, QtWidgets.QTableWidgetItem(origine))
                        # colonne 1 : DLC extraite si présente
                        dlc = extraire_dlc_from_scan(origine)
                        if dlc:
                            self.setItem(ligne, 1, QtWidgets.QTableWidgetItem(dlc))
                        else:
                            # s'assurer que la cellule DLC existe vide (pour clarté)
                            self.setItem(ligne, 1, QtWidgets.QTableWidgetItem(""))
                        ligne += 1
                    self.blockSignals(False)
                    self.assurer_ligne_vide()
                    # notifier la fenêtre principale pour mettre à jour le total
                    fenetre = self.window()
                    if hasattr(fenetre, "mettre_a_jour_total"):
                        try:
                            fenetre.mettre_a_jour_total()
                        except Exception:
                            pass
                    return
        super().keyPressEvent(evenement)

    def assurer_ligne_vide(self):
        """
        Garantit qu'il existe toujours au moins une ligne vide à la fin
        pour l'insertion rapide (ergonomie scanner).
        On considère ligne vide si la colonne Poids (0) est vide.
        """
        derniere_ligne = self.rowCount() - 1
        if derniere_ligne < 0:
            self.setRowCount(1)
            # initialiser cellule DLC
            if self.columnCount() < 2:
                self.setColumnCount(2)
            self.setItem(0, 1, QtWidgets.QTableWidgetItem(""))
            return
        derniere_item = self.item(derniere_ligne, 0)
        if derniere_item is not None and derniere_item.text().strip() != "":
            self.setRowCount(self.rowCount() + 1)
            # créer cellule DLC vide pour la nouvelle ligne
            self.setItem(self.rowCount() - 1, 1, QtWidgets.QTableWidgetItem(""))
        if self.rowCount() == 0:
            self.setRowCount(1)
            self.setItem(0, 1, QtWidgets.QTableWidgetItem(""))


def resource_path(relative_path):
    """
    Obtient le chemin absolu d'une ressource, en tenant compte
    de l'exécution en tant que script ou en tant qu'EXE PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Exécution depuis un exécutable PyInstaller
        base_path = sys._MEIPASS
    else:
        # Exécution en tant que script normal
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class FenetrePrincipalePV(QtWidgets.QMainWindow):
    """
    Fenêtre principale de l'application PV.
    Contient le champ de scan, la table des poids et DLC,
    les contrôles de zoom, le bouton audio pour mettre en muet, le bouton "Créer CSV", le bouton nettoyer,
    le bouton Parse manuel, et le champ total affiché.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Poids Variable Inventaire")
        self.setWindowIcon(QtGui.QIcon(resource_path("favicon.ico")))
        self.resize(720, 460)
        self.son_active = True

        zone_centrale = QtWidgets.QWidget()
        self.setCentralWidget(zone_centrale)
        mise_en_page = QtWidgets.QVBoxLayout(zone_centrale)

        # Ligne supérieure : champ scan à gauche, boutons +/−/info à droite
        mise_haut = QtWidgets.QHBoxLayout()

        self.champ_scan = QtWidgets.QLineEdit()
        self.champ_scan.setPlaceholderText("Entrée scanner")
        self.champ_scan.setFixedWidth(160)
        self.champ_scan.returnPressed.connect(self.lors_retour_scan)
        self.champ_scan.installEventFilter(self)

        mise_haut.addWidget(self.champ_scan)
        mise_haut.addStretch()
        # Bouton Parse manuel
        self.bouton_parse_manuel = QtWidgets.QPushButton("Parse manuel")
        self.bouton_parse_manuel.setToolTip("Parser manuellement un code-barres avec position du poids et décimale")
        self.bouton_parse_manuel.clicked.connect(self.parse_manuel)
        mise_haut.addWidget(self.bouton_parse_manuel)
        # Zoom et info à droite
        self.zoom_moins = QtWidgets.QPushButton("−")
        self.zoom_moins.setFixedSize(28, 28)
        self.zoom_moins.setToolTip("Réduire la taille de l'interface")
        self.zoom_moins.clicked.connect(lambda: self.ajuster_echelle(-0.1))
        mise_haut.addWidget(self.zoom_moins)
        self.zoom_plus = QtWidgets.QPushButton("+")
        self.zoom_plus.setFixedSize(28, 28)
        self.zoom_plus.setToolTip("Augmenter la taille de l'interface")
        self.zoom_plus.clicked.connect(lambda: self.ajuster_echelle(+0.1))
        mise_haut.addWidget(self.zoom_plus)
        # Bouton audio pour mettre en muet
        self.bouton_audio = QtWidgets.QPushButton("🔊")
        self.bouton_audio.setFixedSize(28, 28)
        self.bouton_audio.setToolTip("Activer/Désactiver le son")
        self.bouton_audio.clicked.connect(self.basculer_son)
        mise_haut.addWidget(self.bouton_audio)
        icone_info = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.bouton_info = QtWidgets.QPushButton()
        self.bouton_info.setIcon(icone_info)
        self.bouton_info.setFixedSize(28, 28)
        self.bouton_info.setToolTip("Aide / À propos")
        self.bouton_info.clicked.connect(self.afficher_a_propos)
        mise_haut.addWidget(self.bouton_info)
        mise_en_page.addLayout(mise_haut)

        # Table des poids (2 colonnes : Poids en kg, DLC)
        self.table = TablePV(1, 2)
        self.table.setHorizontalHeaderLabels(["Poids en kg", "DLC"])
        en_tete = self.table.horizontalHeader()
        en_tete.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        en_tete.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
            | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setRowCount(1)
        # initialiser cellule DLC vide
        self.table.setItem(0, 1, QtWidgets.QTableWidgetItem(""))

        mise_en_page.addWidget(self.table, 1)

        # Boutons et affichage du total (QLineEdit en lecture seule mais sélectionnable)
        mise_boutons = QtWidgets.QHBoxLayout()
        # Bouton créé remplaçant "Somme"
        self.bouton_somme = QtWidgets.QPushButton("Créer CSV")
        self.bouton_somme.clicked.connect(self.lors_clic_creer_csv)
        mise_boutons.addWidget(self.bouton_somme)

        self.champ_total = QtWidgets.QLineEdit()
        self.champ_total.setReadOnly(True)
        self.champ_total.setMinimumWidth(10)
        self.champ_total.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        # texte initial
        self.champ_total.setText("Totale : 0.000")
        self.champ_total.setFixedWidth(120)
        mise_boutons.addWidget(self.champ_total)

        # Champ commentaire à droite (label non interactif)
        self.etiquette_commentaire = QtWidgets.QLabel("")
        self.etiquette_commentaire.setMinimumWidth(10)
        self.etiquette_commentaire.setStyleSheet("color: red; padding-left: 10px;")
        self.etiquette_commentaire.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        mise_boutons.addWidget(self.etiquette_commentaire)

        # Bouton Nettoyer (à droite)
        mise_boutons.addStretch()
        self.bouton_effacer = QtWidgets.QPushButton("Nettoyer")
        self.bouton_effacer.setToolTip("Vider toutes les données (confirmation demandée)")
        self.bouton_effacer.clicked.connect(self.confirmer_et_effacer)
        mise_boutons.addWidget(self.bouton_effacer)

        mise_en_page.addLayout(mise_boutons)

        # État pour le contrôle d'échelle
        self.facteur_echelle = 1.0
        # métriques de base pour redimensionnement
        app_font = QtWidgets.QApplication.instance().font()
        try:
            self.taille_police_base = float(app_font.pointSizeF())
        except Exception:
            self.taille_police_base = 9.0

        # Connexions
        self.table.cellChanged.connect(self.lors_changement_cellule)

        # Assurer ligne vide
        self.table.assurer_ligne_vide()

        # Focaliser le champ scan au démarrage (léger délai pour que la fenêtre soit prête)
        QtCore.QTimer.singleShot(100, self.focaliser_champ_scan)

    def focaliser_champ_scan(self):
        """
        Donne le focus au champ de scan et sélectionne son contenu.
        """
        self.champ_scan.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        self.champ_scan.selectAll()

    def eventFilter(self, obj, evenement):
        """
        Intercepte le collage (Ctrl/Cmd+V) dans le champ de scan pour gérer
        le collage multi-lignes et insérer chaque ligne.
        """
        if obj is self.champ_scan and evenement.type() == QtCore.QEvent.Type.KeyPress:
            key_event = evenement
            controle = (key_event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
            meta = (key_event.modifiers() & QtCore.Qt.KeyboardModifier.MetaModifier)
            if (controle or meta) and key_event.key() == QtCore.Qt.Key.Key_V:
                presse_papiers = QtWidgets.QApplication.clipboard()
                texte = presse_papiers.text()
                if texte:
                    lignes = texte.splitlines()
                    for ligne in lignes:
                        self.inserer_ligne_scannee(ligne)
                    self.champ_scan.clear()
                    QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)
                    return True
        return super().eventFilter(obj, evenement)

    def inserer_ligne_scannee(self, ligne: str):
        """
        Insère une ligne scannée dans la première ligne vide de la table.
        Tente de formater la ligne immédiatement. Extrait la DLC (AI 15)
        si présente et valide, et la met en colonne 1.
        Fournit feedback sonore et visuel après insertion.
        """
        if ligne is None:
            return
        texte = ligne.strip()
        if texte == "":
            return
        # trouver première ligne vide (colonne poids)
        ligne_cible = None
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is None or item.text().strip() == "":
                ligne_cible = r
                break
        if ligne_cible is None:
            ligne_cible = self.table.rowCount()
            self.table.setRowCount(self.table.rowCount() + 1)
        # mettre le texte brut puis formater si possible
        self.table.blockSignals(True)
        # colonne 0 : poids (formaté si possible)
        formate = formater_ligne(texte)
        if formate:
            self.table.setItem(ligne_cible, 0, QtWidgets.QTableWidgetItem(formate))
        else:
            self.table.setItem(ligne_cible, 0, QtWidgets.QTableWidgetItem(texte))
        # colonne 1 : DLC extraite si présente
        dlc = extraire_dlc_from_scan(texte)
        if dlc:
            self.table.setItem(ligne_cible, 1, QtWidgets.QTableWidgetItem(dlc))
        else:
            self.table.setItem(ligne_cible, 1, QtWidgets.QTableWidgetItem(""))
        self.table.blockSignals(False)
        # assurer une ligne vide et mettre à jour le total
        self.table.assurer_ligne_vide()
        self.mettre_a_jour_total()
        # feedback sonore
        est_erreur = self.etiquette_commentaire.text().strip() != ""
        if self.son_active:
            if winsound:
                try:
                    if not est_erreur:
                        # succès : court et aigu
                        winsound.Beep(2000, 100)
                    else:
                        # erreur : grave et double
                        winsound.Beep(400, 150)
                        winsound.Beep(400, 150)
                except Exception:
                    QtWidgets.QApplication.beep()
            else:
                QtWidgets.QApplication.beep()
        # feedback visuel : vert si pas d'erreur, rouge si commentaire d'erreur présent
        couleur_flash = "#ff4d4d" if est_erreur else "#4df164"
        self.flash_visuel(color=couleur_flash)

    def lors_retour_scan(self):
        """
        Appelé lorsque l'utilisateur appuie sur RETURN dans le champ de scan.
        Insère chaque ligne présente dans le champ.
        """
        texte = self.champ_scan.text() or ""
        lignes = texte.splitlines()
        for ligne in lignes:
            self.inserer_ligne_scannee(ligne)
        self.champ_scan.clear()
        QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)

    def parse_manuel(self):
        """
        Ouvre une boîte de dialogue avec un champ de scan pour parser manuellement un code-barres.
        Permet de saisir le poids et la décimale manuellement, et de sauvegarder le pattern pour les codes similaires.
        """
        # Créer la boîte de dialogue
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Parse manuel")
        dialog.setModal(True)
        dialog.resize(500, 100)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Ligne du haut : label "Code-barres:" à gauche, boutons à droite
        layout_haut = QtWidgets.QHBoxLayout()
        layout_haut.addWidget(QtWidgets.QLabel("Code-barres:"))
        layout_haut.addStretch()
        
        # Bouton pour gérer les patterns
        bouton_gerer_patterns = QtWidgets.QPushButton("Gérer les patterns")
        bouton_gerer_patterns.setToolTip("Voir et supprimer les patterns sauvegardés")
        bouton_gerer_patterns.clicked.connect(lambda: self.gerer_patterns(dialog))
        layout_haut.addWidget(bouton_gerer_patterns)
        
        icone_info = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation)
        bouton_info_instructions = QtWidgets.QPushButton()
        bouton_info_instructions.setIcon(icone_info)
        bouton_info_instructions.setFixedSize(24, 24)
        bouton_info_instructions.setToolTip("Aide - Instructions pour utiliser les marqueurs")
        def afficher_instructions():
            texte_instructions = (
                "<b>Instructions pour le parsing manuel :</b><br><br>"
                "Scannez un code-barres, puis éditez-le en insérant des marqueurs :<br><br>"
                " <b>&gt;</b> pour marquer le début du poids<br>"
                " <b>,</b> pour marquer la position de la décimale (optionnel)<br>"
                " <b>&lt;</b> pour marquer la fin du poids<br><br>"
                "Vous pouvez utiliser les boutons en dessous du champ pour insérer les marqueurs,<br>"
                "ou les taper directement au clavier.<br>"
                "Assurez-vous qu'apres &gt; il y et assez de zéros de remplissage pour capturer les poids avec dizaines ou centaines si d'autres codes-barres en ont."
            )
            QtWidgets.QMessageBox.information(
                dialog,
                "Instructions - Parse manuel",
                texte_instructions
            )
        bouton_info_instructions.clicked.connect(afficher_instructions)
        layout_haut.addWidget(bouton_info_instructions)
        layout.addLayout(layout_haut)
        
        # Champ de scan dans la boîte de dialogue
        layout_scan = QtWidgets.QHBoxLayout()
        champ_scan_dialog = QtWidgets.QLineEdit()
        champ_scan_dialog.setPlaceholderText("Scannez le code, puis insérez > , < pour marquer le poids")
        champ_scan_dialog.returnPressed.connect(dialog.accept)
        layout_scan.addWidget(champ_scan_dialog)
        layout.addLayout(layout_scan)
        
        # Fonction pour insérer un caractère à la position du curseur
        def inserer_marqueur(caractere: str):
            cursor_pos = champ_scan_dialog.cursorPosition()
            texte = champ_scan_dialog.text()
            nouveau_texte = texte[:cursor_pos] + caractere + texte[cursor_pos:]
            champ_scan_dialog.setText(nouveau_texte)
            # Repositionner le curseur après le caractère inséré
            champ_scan_dialog.setCursorPosition(cursor_pos + 1)
            champ_scan_dialog.setFocus()
        
        # Boutons pour insérer les marqueurs (en dessous du champ de scan)
        layout_boutons_marqueurs = QtWidgets.QHBoxLayout()
        layout_boutons_marqueurs.addStretch()  # Aligner à droite ou centrer
        
        bouton_debut = QtWidgets.QPushButton(">")
        bouton_debut.setToolTip("Insérer '>' pour marquer le début du poids")
        bouton_debut.setFixedSize(30, 30)
        bouton_debut.clicked.connect(lambda: inserer_marqueur('>'))
        layout_boutons_marqueurs.addWidget(bouton_debut)
        
        bouton_decimal = QtWidgets.QPushButton(",")
        bouton_decimal.setToolTip("Insérer ',' pour marquer la position de la décimale")
        bouton_decimal.setFixedSize(30, 30)
        bouton_decimal.clicked.connect(lambda: inserer_marqueur(','))
        layout_boutons_marqueurs.addWidget(bouton_decimal)
        
        bouton_fin = QtWidgets.QPushButton("<")
        bouton_fin.setToolTip("Insérer '<' pour marquer la fin du poids")
        bouton_fin.setFixedSize(30, 30)
        bouton_fin.clicked.connect(lambda: inserer_marqueur('<'))
        layout_boutons_marqueurs.addWidget(bouton_fin)
        
        layout_boutons_marqueurs.addStretch()  # Aligner à droite ou centrer
        layout.addLayout(layout_boutons_marqueurs)
        
        # Aperçu du résultat
        label_apercu = QtWidgets.QLabel("Aperçu: -")
        label_apercu.setStyleSheet("font-weight: bold; padding: 5px; font-size: 14px;")
        label_apercu.setTextFormat(QtCore.Qt.TextFormat.RichText)  # Activer le support HTML
        layout.addWidget(label_apercu)
        
        def parser_avec_marqueurs(code_avec_marqueurs: str) -> Tuple[Optional[str], Optional[Dict]]:
            """
            Parse le code avec les marqueurs spéciaux (> , <).
            Retourne (poids_formate, pattern_dict) ou (None, None) si invalide.
            """
            if not code_avec_marqueurs:
                return None, None
            
            # Trouver les positions des marqueurs
            pos_debut_marqueur = code_avec_marqueurs.find('>')
            pos_decimal_marqueur = code_avec_marqueurs.find(',')
            pos_fin_marqueur = code_avec_marqueurs.find('<')
            
            # Les marqueurs > et < sont obligatoires
            if pos_debut_marqueur == -1 or pos_fin_marqueur == -1:
                return None, None
            
            # Extraire le code original (sans les marqueurs)
            code_original = code_avec_marqueurs.replace('>', '').replace(',', '').replace('<', '')
            
            # Calculer les positions dans le code original
            # On doit compter combien de marqueurs sont avant chaque position
            def compter_marqueurs_avant(pos: int) -> int:
                count = 0
                for i in range(pos):
                    if code_avec_marqueurs[i] in '>,<':
                        count += 1
                return count
            
            pos_debut = pos_debut_marqueur - compter_marqueurs_avant(pos_debut_marqueur)
            
            # Déterminer la fin du poids (le marqueur < est obligatoire)
            pos_fin = pos_fin_marqueur - compter_marqueurs_avant(pos_fin_marqueur)
            longueur = pos_fin - pos_debut
            
            # Extraire le poids brut
            if longueur > 0:
                poids_brut = code_original[pos_debut:pos_debut + longueur]
            else:
                poids_brut = code_original[pos_debut:]
            
            # Déterminer la position de la décimale
            pos_decimal = -1
            if pos_decimal_marqueur != -1:
                # La position de la décimale est relative au début du poids
                pos_decimal_dans_code = pos_decimal_marqueur - compter_marqueurs_avant(pos_decimal_marqueur)
                pos_decimal = pos_decimal_dans_code - pos_debut
                # Vérifier que la décimale est dans le poids
                if pos_decimal < 0 or pos_decimal >= len(poids_brut):
                    pos_decimal = -1
            
            # Formater le poids
            if pos_decimal >= 0 and pos_decimal < len(poids_brut):
                partie_entiere = poids_brut[:pos_decimal]
                partie_decimale = poids_brut[pos_decimal:]
                poids_formate = partie_entiere + "," + partie_decimale
                try:
                    partie_entiere_int = str(int(partie_entiere)) if partie_entiere else "0"
                    poids_formate = partie_entiere_int + "," + partie_decimale
                except ValueError:
                    pass
            else:
                poids_formate = poids_brut
                try:
                    poids_formate = str(int(poids_brut))
                except ValueError:
                    pass
            
            # Créer le pattern pour sauvegarde
            pattern = {
                'pos_debut': pos_debut,
                'pos_decimal': pos_decimal,
                'longueur': longueur,
                'longueur_code': len(code_original),
                'prefixe': code_original[:2] if len(code_original) >= 2 else ""
            }
            
            return poids_formate, pattern
        
        def mettre_a_jour_apercu():
            """Met à jour l'aperçu du poids formaté"""
            code_avec_marqueurs = champ_scan_dialog.text().strip()
            if not code_avec_marqueurs:
                label_apercu.setText("Aperçu: -")
                return
            
            # Parser avec les marqueurs
            poids_formate, pattern = parser_avec_marqueurs(code_avec_marqueurs)
            
            # Trouver les positions des marqueurs
            pos_debut_marqueur = code_avec_marqueurs.find('>')
            pos_fin_marqueur = code_avec_marqueurs.find('<')
            
            # Si les deux marqueurs > et < sont présents et que le parsing fonctionne
            if pos_debut_marqueur != -1 and pos_fin_marqueur != -1 and poids_formate:
                # Afficher uniquement le poids formaté en gras
                label_apercu.setText(f"<b>Aperçu: {poids_formate}</b>")
                return
            
            # Sinon, afficher le code-barres avec opacité sur les parties supprimées
            html_parts = ["Aperçu: "]
            
            for i, char in enumerate(code_avec_marqueurs):
                # Ignorer les marqueurs (ne pas les afficher)
                if char in '>,<':
                    continue
                
                # Déterminer si le caractère doit être opacifié
                doit_etre_opacifie = False
                if pos_debut_marqueur != -1 and i < pos_debut_marqueur:
                    # Avant > : opacité 0.4
                    doit_etre_opacifie = True
                elif pos_fin_marqueur != -1 and i > pos_fin_marqueur:
                    # Après < : opacité 0.4
                    doit_etre_opacifie = True
                
                # Échapper les caractères HTML spéciaux
                char_escaped = char.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                if doit_etre_opacifie:
                    # Utiliser rgba() pour l'opacité (plus compatible avec QLabel RichText)
                    # #2d2d2d avec opacité 0.4
                    html_parts.append(f'<span style="color: rgba(45, 45, 45, 0.4);">{char_escaped}</span>')
                else:
                    html_parts.append(char_escaped)
            
            label_apercu.setText(''.join(html_parts))
        
        # Connecter le signal pour mettre à jour l'aperçu
        champ_scan_dialog.textChanged.connect(mettre_a_jour_apercu)
        
        # Boutons
        boutons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        boutons.accepted.connect(dialog.accept)
        boutons.rejected.connect(dialog.reject)
        layout.addWidget(boutons)
        
        # Focus sur le champ de scan
        champ_scan_dialog.setFocus()
        
        # Afficher la boîte de dialogue
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            code_avec_marqueurs = champ_scan_dialog.text().strip()
            if not code_avec_marqueurs:
                return
            
            # Parser avec les marqueurs
            poids_formate, pattern = parser_avec_marqueurs(code_avec_marqueurs)
            
            if not poids_formate or not pattern:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Parse manuel",
                    "Impossible de parser le code. Assurez-vous d'avoir inséré les marqueurs '>' et '<' pour indiquer le début et la fin du poids."
                )
                return
            
            # Sauvegarder le pattern
            patterns = charger_patterns()
            # Créer une clé basée sur la longueur et le préfixe (2 premiers caractères)
            code_original = code_avec_marqueurs.replace('>', '').replace(',', '').replace('<', '')
            pattern_key = f"len_{pattern['longueur_code']}_pref_{pattern['prefixe']}"
            patterns[pattern_key] = pattern
            sauvegarder_patterns(patterns)
            
            # Le pattern est sauvegardé, mais le poids n'est pas ajouté à la table
            # Il sera utilisé automatiquement pour les codes similaires non reconnus
            QtWidgets.QMessageBox.information(
                self,
                "Pattern sauvegardé",
                f"Le pattern a été sauvegardé avec succès.\n\nPoids détecté: {poids_formate}\n\nCe pattern sera utilisé automatiquement pour les codes-barres similaires\n(prefixes {pattern['prefixe']} et longueur {pattern['longueur_code']})."
            )
            QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)

    def gerer_patterns(self, parent_dialog=None):
        """
        Ouvre une boîte de dialogue pour gérer les patterns sauvegardés.
        Permet de voir et supprimer les patterns.
        """
        dialog_gerer = QtWidgets.QDialog(self if parent_dialog is None else parent_dialog)
        dialog_gerer.setWindowTitle("Gérer les patterns")
        dialog_gerer.setModal(True)
        dialog_gerer.resize(600, 400)
        layout_gerer = QtWidgets.QVBoxLayout(dialog_gerer)
        
        # Label d'information
        label_info = QtWidgets.QLabel(
            "Patterns sauvegardés pour le parsing manuel. Sélectionnez un pattern pour le supprimer."
        )
        label_info.setWordWrap(True)
        layout_gerer.addWidget(label_info)
        
        # Table pour afficher les patterns
        table_patterns = QtWidgets.QTableWidget()
        table_patterns.setColumnCount(6)
        table_patterns.setHorizontalHeaderLabels(["Clé", "Longueur code", "Préfixe", "Début", "Décimale", "Longueur"])
        table_patterns.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table_patterns.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        layout_gerer.addWidget(table_patterns)
        
        def charger_et_afficher_patterns():
            """Charge et affiche les patterns dans la table"""
            patterns = charger_patterns()
            table_patterns.setRowCount(len(patterns))
            row = 0
            for pattern_key, pattern in patterns.items():
                table_patterns.setItem(row, 0, QtWidgets.QTableWidgetItem(pattern_key))
                table_patterns.setItem(row, 1, QtWidgets.QTableWidgetItem(str(pattern.get('longueur_code', ''))))
                table_patterns.setItem(row, 2, QtWidgets.QTableWidgetItem(pattern.get('prefixe', '')))
                table_patterns.setItem(row, 3, QtWidgets.QTableWidgetItem(str(pattern.get('pos_debut', ''))))
                decimale = pattern.get('pos_decimal', -1)
                table_patterns.setItem(row, 4, QtWidgets.QTableWidgetItem(str(decimale) if decimale >= 0 else "Aucune"))
                longueur = pattern.get('longueur', 0)
                table_patterns.setItem(row, 5, QtWidgets.QTableWidgetItem(str(longueur) if longueur > 0 else "Jusqu'à la fin"))
                row += 1
            table_patterns.resizeColumnsToContents()
        
        # Charger les patterns au démarrage
        charger_et_afficher_patterns()
        
        # Boutons
        layout_boutons = QtWidgets.QHBoxLayout()
        
        bouton_supprimer = QtWidgets.QPushButton("Supprimer le pattern sélectionné")
        def supprimer_pattern():
            row = table_patterns.currentRow()
            if row < 0:
                QtWidgets.QMessageBox.warning(
                    dialog_gerer,
                    "Supprimer pattern",
                    "Veuillez sélectionner un pattern à supprimer."
                )
                return
            
            pattern_key = table_patterns.item(row, 0).text()
            reponse = QtWidgets.QMessageBox.question(
                dialog_gerer,
                "Confirmer la suppression",
                f"Voulez-vous vraiment supprimer le pattern '{pattern_key}' ?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reponse == QtWidgets.QMessageBox.StandardButton.Yes:
                patterns = charger_patterns()
                if pattern_key in patterns:
                    del patterns[pattern_key]
                    sauvegarder_patterns(patterns)
                    charger_et_afficher_patterns()
                    QtWidgets.QMessageBox.information(
                        dialog_gerer,
                        "Pattern supprimé",
                        f"Le pattern '{pattern_key}' a été supprimé."
                    )
        bouton_supprimer.clicked.connect(supprimer_pattern)
        layout_boutons.addWidget(bouton_supprimer)
        
        bouton_tout_supprimer = QtWidgets.QPushButton("Supprimer tous les patterns")
        def supprimer_tous():
            patterns = charger_patterns()
            if not patterns:
                QtWidgets.QMessageBox.information(
                    dialog_gerer,
                    "Aucun pattern",
                    "Il n'y a aucun pattern à supprimer."
                )
                return
            
            reponse = QtWidgets.QMessageBox.question(
                dialog_gerer,
                "Confirmer la suppression",
                f"Voulez-vous vraiment supprimer tous les {len(patterns)} patterns ?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reponse == QtWidgets.QMessageBox.StandardButton.Yes:
                sauvegarder_patterns({})
                charger_et_afficher_patterns()
                QtWidgets.QMessageBox.information(
                    dialog_gerer,
                    "Patterns supprimés",
                    "Tous les patterns ont été supprimés."
                )
        bouton_tout_supprimer.clicked.connect(supprimer_tous)
        layout_boutons.addWidget(bouton_tout_supprimer)
        
        layout_boutons.addStretch()
        
        bouton_fermer = QtWidgets.QPushButton("Fermer")
        bouton_fermer.clicked.connect(dialog_gerer.accept)
        layout_boutons.addWidget(bouton_fermer)
        
        layout_gerer.addLayout(layout_boutons)
        
        # Afficher la boîte de dialogue
        dialog_gerer.exec()

    def lors_changement_cellule(self, ligne: int, colonne: int):
        """
        Géré lorsque le contenu d'une cellule change (édition manuelle).
        - Si édition de la colonne Poids (0) : tente de formatter la cellule,
          essaie d'extraire une DLC (si le texte ressemble à un scan long)
          et met à jour la cellule DLC (colonne 1) en conséquence.
        - Si édition d'autres colonnes : on laisse tel quel (utilisateur libre).
        Après modification, assure une ligne vide, remet le focus sur le champ scan,
        et met à jour le total.
        """
        item = self.table.item(ligne, colonne)
        if item is None:
            return
        texte = item.text()
        if texte is None or texte.strip() == "":
            # si la cellule poids a été effacée, on efface aussi la DLC correspondante
            if colonne == 0:
                self.table.blockSignals(True)
                self.table.setItem(ligne, 1, QtWidgets.QTableWidgetItem(""))
                self.table.blockSignals(False)
            QtCore.QTimer.singleShot(0, self.table.assurer_ligne_vide)
            # mettre à jour le total (au cas où une valeur a été effacée)
            QtCore.QTimer.singleShot(0, self.mettre_a_jour_total)
            return

        # si édition de la colonne poids, tenter formatage et extraction DLC à partir du texte fourni
        if colonne == 0:
            # tenter formatter le poids
            formate = formater_ligne(texte)
            self.table.blockSignals(True)
            if formate:
                self.table.setItem(ligne, 0, QtWidgets.QTableWidgetItem(formate))
            # tenter d'extraire DLC depuis le texte brut (utile si l'utilisateur a collé un code)
            dlc = extraire_dlc_from_scan(texte)
            if dlc:
                self.table.setItem(ligne, 1, QtWidgets.QTableWidgetItem(dlc))
            else:
                # ne pas écraser une DLC existante si l'utilisateur l'a mise manuellement,
                # mais si le texte ressemble clairement à un scan (long) et aucune DLC présente,
                # on met une cellule vide pour clarté
                existant = self.table.item(ligne, 1)
                if existant is None:
                    self.table.setItem(ligne, 1, QtWidgets.QTableWidgetItem(""))
            self.table.blockSignals(False)

        QtCore.QTimer.singleShot(0, self.table.assurer_ligne_vide)
        # retour du focus au champ scan pour ergonomie
        QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)
        # mise à jour du total après modification
        QtCore.QTimer.singleShot(0, self.mettre_a_jour_total)

    def mettre_a_jour_total(self):
        """
        Parcourt la table, calcule la somme des valeurs valides (uniquement la colonne Poids),
        met à jour le champ total et affiche un message d'erreur si une ligne semble suspecte.
        Détecte la première ligne erronée (valeur > 50 ou entre 0 et 0.01).
        La colonne DLC n'est pas prise en compte.
        """
        total = 0.0
        premiere_ligne_erreur = None
        for r in range(self.table.rowCount()):
            cellule = self.table.item(r, 0)  # colonne Poids uniquement
            if cellule is None:
                continue
            texte = cellule.text().strip()
            if texte == "":
                continue
            formate = formater_ligne(texte)
            if formate:
                valeur = valeur_formatee_vers_float(formate)
            else:
                valeur = valeur_formatee_vers_float(texte)
            if (valeur > 50 or (valeur > 0 and valeur < 0.01)) and premiere_ligne_erreur is None:
                premiere_ligne_erreur = r + 1
            total += valeur
        # mise à jour du QLineEdit (sélectionnable)
        self.champ_total.setText(f"Totale : {total:.3f}")
        # affichage du message d'erreur si nécessaire
        if premiere_ligne_erreur is not None:
            self.etiquette_commentaire.setText(f"Erreur de saisie ligne {premiere_ligne_erreur}")
            self.etiquette_commentaire.setStyleSheet("color: red; padding-left: 10px;")
        else:
            self.etiquette_commentaire.setText("")
            self.etiquette_commentaire.setStyleSheet("")

    # --------------------------
    # Méthodes utilitaires
    # --------------------------
    def flash_visuel(self, color="#4df164", duration_ms: int = 220):
        """
        Flash visuel coloré (vert ou rouge) sur tout le fond. Gère
        enchaînements multiples de flashs sans perdre la couleur d'origine.
        """
        try:
            central = self.centralWidget()
            # mémoriser la couleur d'origine (une seule fois)
            if not hasattr(self, '_flash_orig_bg') or self._flash_orig_bg is None:
                self._flash_orig_bg = central.styleSheet()
            # compteur de flashs actifs
            if not hasattr(self, '_flash_count') or self._flash_count is None:
                self._flash_count = 0
            self._flash_count += 1
            central.setStyleSheet(f"background-color: {color};")
            def terminer_flash():
                self._flash_count -= 1
                if self._flash_count <= 0:
                    central.setStyleSheet(self._flash_orig_bg)
                    self._flash_count = 0
            QtCore.QTimer.singleShot(duration_ms, terminer_flash)
        except Exception:
            pass

    def confirmer_et_effacer(self):
        """
        Demande confirmation avant de tout effacer.
        """
        reponse = QtWidgets.QMessageBox.question(
            self,
            "Confirmer la suppression",
            "Voulez-vous vraiment supprimer toutes les données actuelles ?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reponse == QtWidgets.QMessageBox.StandardButton.Yes:
            self.tout_effacer()

    def tout_effacer(self):
        """
        Vide complètement la table et réinitialise l'état de l'interface.
        La colonne DLC (colonne 1) est bien effacée également.
        """
        self.table.blockSignals(True)
        self.table.clearContents()
        # conserver 2 colonnes
        self.table.setColumnCount(2)
        self.table.setRowCount(1)
        # initialiser DLC de la première ligne
        self.table.setItem(0, 1, QtWidgets.QTableWidgetItem(""))
        self.table.blockSignals(False)
        self.table.assurer_ligne_vide()
        # réinitialiser total et commentaires
        self.champ_total.setText("Totale : 0.000")
        self.etiquette_commentaire.setText("")
        # replacer le focus sur le champ scan
        QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)

    def afficher_a_propos(self):
        """
        Affiche une boîte 'À propos' expliquant le parser et les informations
        sur l'auteur.
        """
        about_text = (
            "<b>PV – Poids Variable (Inventaire produits alimentaires)</b><br><br>"
            "Application de bureau développée pour la saisie rapide de codes-barres à poids variable.<br><br>"
            "<b>Fonctionnement du parser :</b><br>"
            "- Si le code a <b>13 chiffres</b> (format EAN-13) : extrait les 5 caractères (positions 7–11) → format “xx,xxx”.<br>"
            "- Pour les codes <b>GS1</b> : parse séquentiellement les identifiants d'application (IA) selon la norme GS1 :<br>"
            "  • IA <b>01</b> : GTIN (14 chiffres)<br>"
            "  • IA <b>310x</b> : Poids net en kg (6 chiffres, x = nombre de décimales, ex. <i>3103</i> → 3 décimales)<br>"
            "  • IA <b>15</b> : Date limite de consommation (6 chiffres AAMMJJ) lorsqu'il est rencontré affiche la DLC dans la colonne.<br>"
            "  • IA <b>autres</b> : autres IA GS1 sont ignorées.<br>"
            "- <b>Parse manuel</b> : pour les codes non reconnus, utilisez le bouton 'Parse manuel' pour définir "
            "manuellement la position du poids avec les marqueurs <b>&gt;</b> (début), <b>,</b> (décimale), <b>&lt;</b> (fin). "
            "Le pattern est sauvegardé et réutilisé automatiquement pour les codes similaires.<br><br>"
            "<b>Raccourcis :</b><br>"
            "- Champ 'Entrée scanner' : reçoit les scans successifs (pas besoin de cliquer).<br>"
            "- 'Créer CSV' : exporte la table (colonnes Poids et DLC) en fichier CSV.<br>"
            "- 'Nettoyer' : vide l'inventaire après confirmation (efface aussi DLC).<br>"
            "- 'Parse manuel' : permet de définir manuellement le parsing pour les codes non reconnus.<br><br>"
            "<b>Créé par :</b><br>"
            "WWW.GAIGHER.FR / Siret: 798 691 598 00014"
        )
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("À propos - PV")
        msg_box.setText(about_text)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.NoIcon)
        msg_box.exec()

    def ajuster_echelle(self, delta: float):
        """
        Ajuste le facteur d'échelle global (zoom UI). delta positif agrandit,
        delta négatif réduit. Clamp entre 0.7 et 2.0.
        """
        nouvelle_echelle = self.facteur_echelle + delta
        nouvelle_echelle = max(0.7, min(2.0, nouvelle_echelle))
        if abs(nouvelle_echelle - self.facteur_echelle) < 0.001:
            return
        self.facteur_echelle = nouvelle_echelle
        # mettre à jour la police de l'application
        app = QtWidgets.QApplication.instance()
        if app is not None:
            police = app.font()
            police.setPointSizeF(self.taille_police_base * self.facteur_echelle)
            app.setFont(police)
        # adapter quelques widgets à largeur fixe
        self.champ_total.setFixedWidth(int(120 * self.facteur_echelle))
        self.etiquette_commentaire.setFixedWidth(int(120 * self.facteur_echelle))
        # ajuster la taille des boutons
        self.zoom_moins.setFixedSize(int(28 * self.facteur_echelle), int(28 * self.facteur_echelle))
        self.zoom_plus.setFixedSize(int(28 * self.facteur_echelle), int(28 * self.facteur_echelle))
        self.bouton_audio.setFixedSize(int(28 * self.facteur_echelle), int(28 * self.facteur_echelle))
        self.bouton_info.setFixedSize(int(28 * self.facteur_echelle), int(28 * self.facteur_echelle))
        self.bouton_effacer.setFixedHeight(max(22, int(24 * self.facteur_echelle)))
        self.bouton_somme.setFixedHeight(max(22, int(24 * self.facteur_echelle)))
        # hauteur du champ scan
        self.champ_scan.setFixedHeight(max(20, int(24 * self.facteur_echelle)))
        # essayer d'ajuster la hauteur des lignes
        try:
            for r in range(self.table.rowCount()):
                self.table.setRowHeight(r, max(18, int(20 * self.facteur_echelle)))
        except Exception:
            pass

    def basculer_son(self):
        """Active ou désactive le feedback sonore"""
        self.son_active = not self.son_active
        if self.son_active:
            self.bouton_audio.setText("🔊")
            self.bouton_audio.setToolTip("Activer/Désactiver le son (actif)")
        else:
            self.bouton_audio.setText("🔇")
            self.bouton_audio.setToolTip("Activer/Désactiver le son (muet)")

    def lors_clic_creer_csv(self):
        """
        Ouvre une boîte de dialogue pour choisir le fichier CSV à enregistrer,
        puis crée le fichier contenant les deux colonnes (Poids en kg, DLC).
        Ne modifie pas la table en mémoire.
        """
        # Suggestion de nom par défaut
        nom_defaut = "inventaire.csv"
        chemin, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Enregistrer le CSV",
            nom_defaut,
            "Fichiers CSV (*.csv);;Tous les fichiers (*)"
        )
        if not chemin:
            return
        try:
            self.creer_csv_fichier(chemin)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Impossible d'enregistrer le CSV :\n{e}")
            return
        QtWidgets.QMessageBox.information(self, "Succès", f"CSV enregistré :\n{chemin}")
        # garder le focus ergonomique sur le champ scan et mettre à jour total
        self.mettre_a_jour_total()
        QtCore.QTimer.singleShot(0, self.focaliser_champ_scan)

    def creer_csv_fichier(self, chemin: str):
        """
        Écrit le fichier CSV au chemin fourni.
        Inclut l'en-tête ["Poids en kg","DLC"].
        Exclut les lignes entièrement vides (les deux colonnes vides).
        Encodage utf-8-sig pour compatibilité Excel.
        """
        lignes = []
        for r in range(self.table.rowCount()):
            item_poids = self.table.item(r, 0)
            item_dlc = self.table.item(r, 1)
            texte_poids = "" if item_poids is None else item_poids.text()
            texte_dlc = "" if item_dlc is None else item_dlc.text()
            if texte_poids.strip() == "" and texte_dlc.strip() == "":
                continue
            lignes.append([texte_poids, texte_dlc])
        # Écrire le CSV
        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Poids en kg", "DLC"])
            writer.writerows(lignes)


def principal():
    """
    Point d'entrée principal de l'application.
    """
    app = QtWidgets.QApplication(sys.argv)
    w = FenetrePrincipalePV()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    principal()
