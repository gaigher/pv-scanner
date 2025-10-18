#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import csv
from datetime import datetime
from typing import Optional

import platform
if platform.system() == "Windows":
    import winsound
else:
    winsound = None

from PyQt6 import QtWidgets, QtCore, QtGui



def formater_ligne(ligne: str):
    """
    Analyse une ligne brute (code scanné) et renvoie une chaîne formatée
    représentant le poids avec une virgule décimale (ex: "1,234").
    Retourne None si la ligne ne correspond pas à un format connu.
    Règles :
    - Si la chaîne fait 13 caractères : extrait positions 7–11 (5 caractères)
      et rend "xx,xxx".
    - Sinon, cherche un segment "310xYYYYYY" dans la position prévue (16:26)
      et applique le découpage en fonction de x (3100..3105).
    """
    if ligne is None:
        return None
    chaine = ligne.strip()
    if len(chaine) == 13:
        extrait = chaine[7:12]
        if len(extrait) >= 5:
            return extrait[0:2] + "," + extrait[2:]
        return None
    if len(chaine) < 26:
        return None
    sous_chaine = chaine[16:26]
    if not sous_chaine.startswith("310"):
        return None
    prefixe = sous_chaine[0:4]
    nombre = sous_chaine[4:]
    formats_map = {
        "3100": lambda n: n,
        "3101": lambda n: (n[:5] + "," + n[5:]) if len(n) > 5 else None,
        "3102": lambda n: (n[:4] + "," + n[4:]) if len(n) > 4 else None,
        "3103": lambda n: (n[:3] + "," + n[3:]) if len(n) > 3 else None,
        "3104": lambda n: (n[:2] + "," + n[2:]) if len(n) > 2 else None,
        "3105": lambda n: (n[:1] + "," + n[1:]) if len(n) > 1 else None,
    }
    fonction_fmt = formats_map.get(prefixe)
    if not fonction_fmt:
        return None
    return fonction_fmt(nombre)


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
    Extrait la DLC (AI 15) du texte fourni en respectant la contrainte
    "à partir du 27ème caractère (index 26)". Renvoie une chaîne au format
    'DD/MM/YYYY' si valide, sinon None.

    - Cherche le motif 15(\d{6}) dans texte[26:].
    - Interprète YYMMDD → 20YY-MM-DD (valide jusqu'en 2099).
    - Si date invalide, retourne None.
    """
    if texte is None:
        return None
    texte_nettoye = texte.strip()
    if len(texte_nettoye) <= 26:
        return None
    reste = texte_nettoye[26:]
    match = re.search(r"15(\d{6})", reste)
    if not match:
        return None
    yymmjj = match.group(1)
    try:
        aa = int(yymmjj[0:2])
        mois = int(yymmjj[2:4])
        jour = int(yymmjj[4:6])
        annee = 2000 + aa  # règle : YY -> 20YY
        date_obj = datetime(annee, mois, jour)  # valider date
    except Exception:
        return None
    return f"{date_obj.day:02d}/{date_obj.month:02d}/{date_obj.year:04d}"


class TablePV(QtWidgets.QTableWidget):
    """
    QTableWidget adapté : gestion améliorée du collage multi-lignes.
    La table a désormais 2 colonnes : [Poids en kg, DLC].
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
    Fenêtre principale de l'application PV (version francisée).
    Contient le champ de scan, la table des poids (avec colonne DLC),
    les contrôles de zoom, le bouton "Créer CSV", le bouton nettoyer, et le champ total affiché.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Poids Variable Inventaire")
        self.setWindowIcon(QtGui.QIcon(resource_path("favicon.ico")))
        self.resize(720, 460)

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
        # feedback sonore amélioré (remplace QApplication.beep)
        est_erreur = self.etiquette_commentaire.text().strip() != ""
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
            "Application de bureau développée pour la saisie rapide de codes-barres GS1 à poids variable.<br><br>"
            "<b>Fonctionnement du parser :</b><br>"
            "- Si le code a <b>13 chiffres</b> : extrait les 5 caractères (positions 7–11) → format “xx,xxx”.<br>"
            "- Si le code contient un segment <b>310xYYYYYY</b> : extrait la valeur selon le chiffre après 310 "
            "(ex. <i>3103</i> → 3 décimales).<br>"
            "- <b>DLC</b> : si le segment <b>15YYMMDD</b> est présent après le 27ᵉ caractère (index 26), il est affiché "
            "dans la colonne DLC au format DD/MM/YYYY (on suppose 20YY pour l'année).<br><br>"
            "<b>Raccourcis :</b><br>"
            "- Champ 'Entrée scanner' : reçoit les scans successifs (pas besoin de cliquer).<br>"
            "- 'Créer CSV' : exporte la table (colonnes Poids et DLC) en fichier CSV.<br>"
            "- 'Nettoyer' : vide l'inventaire après confirmation (efface aussi DLC).<br><br>"
            "<b>Créé par :</b><br>"
            "WWW.GAIGHER.FR / Siret: 798 691 598 00014"
        )
        QtWidgets.QMessageBox.information(self, "À propos - PV", about_text)

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

    # gardons l'ancien nom du slot pour compatibilité si quelque part référencé (non utilisé)
    def lors_clic_somme(self):
        """
        Ancien slot 'Somme' — redirige vers la création du CSV (compatibilité interne).
        """
        self.lors_clic_creer_csv()


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
