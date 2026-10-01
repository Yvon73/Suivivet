/*
 * Tableaux lisibles sur téléphone : sous 768 px de large (cf. section
 * « Mobile » de static/css/style.css), un tableau d'au moins 4 colonnes est
 * réaffiché en une carte par ligne, chaque valeur précédée de l'intitulé de
 * sa colonne — au lieu d'un tableau écrasé qu'il faut faire défiler de côté.
 * Au-delà de 768 px, il reste un tableau classique.
 *
 * Ce script ne fait que recopier l'intitulé de chaque colonne (son <th>)
 * dans un attribut data-label de chaque cellule, que le CSS affiche, et
 * marque la colonne « Actions » (ou sans intitulé) pour que ses boutons
 * s'alignent en bas de la carte. Il pose aussi les rôles ARIA de tableau :
 * passer les cellules en display:block fait perdre aux lecteurs d'écran la
 * sémantique native du <table>, que ces rôles rétablissent.
 *
 * Chargé en fin de <body>, AVANT les scripts propres aux pages (block
 * extra_js de templates/base.html) : les cellules sont étiquetées pendant que
 * toutes les lignes sont encore dans le DOM, avant que DataTables n'en
 * retire celles des pages suivantes. Les lignes ajoutées plus tard (ligne
 * « aucun élément » de DataTables, lignes de ventilation ajoutées dans
 * factures/form.html) sont étiquetées à la volée.
 */
(function () {
    'use strict';

    var NB_COLONNES_MIN = 4;

    function intitulesColonnes(table) {
        var entete = table.tHead;
        if (!entete || !entete.rows.length) {
            return [];
        }
        var intitules = [];
        var cellules = entete.rows[entete.rows.length - 1].cells;
        for (var i = 0; i < cellules.length; i++) {
            var texte = cellules[i].textContent.replace(/\s+/g, ' ').trim();
            for (var n = 0; n < cellules[i].colSpan; n++) {
                intitules.push(texte);
            }
        }
        return intitules;
    }

    function etiqueterLigne(ligne, intitules) {
        ligne.setAttribute('role', 'row');
        var colonne = 0;
        for (var i = 0; i < ligne.cells.length; i++) {
            var cellule = ligne.cells[i];
            var intitule = intitules[colonne];
            colonne += cellule.colSpan;
            cellule.setAttribute('role', 'cell');
            if (cellule.colSpan > 1) {
                continue; // ligne « aucun élément » qui couvre tout le tableau
            }
            if (intitule === '' || intitule === 'Actions') {
                cellule.classList.add('cellule-actions');
            } else if (intitule !== undefined) {
                cellule.setAttribute('data-label', intitule);
            }
        }
    }

    function preparerTableau(table) {
        var intitules = intitulesColonnes(table);
        if (intitules.length < NB_COLONNES_MIN) {
            return;
        }
        table.classList.add('tableau-empilable');
        table.setAttribute('role', 'table');

        var entete = table.tHead;
        entete.setAttribute('role', 'rowgroup');
        for (var r = 0; r < entete.rows.length; r++) {
            entete.rows[r].setAttribute('role', 'row');
            for (var c = 0; c < entete.rows[r].cells.length; c++) {
                entete.rows[r].cells[c].setAttribute('role', 'columnheader');
            }
        }

        for (var b = 0; b < table.tBodies.length; b++) {
            var corps = table.tBodies[b];
            corps.setAttribute('role', 'rowgroup');
            for (var l = 0; l < corps.rows.length; l++) {
                etiqueterLigne(corps.rows[l], intitules);
            }
            new MutationObserver(function (mutations) {
                mutations.forEach(function (mutation) {
                    mutation.addedNodes.forEach(function (noeud) {
                        if (noeud.nodeName === 'TR') {
                            etiqueterLigne(noeud, intitules);
                        }
                    });
                });
            }).observe(corps, {childList: true});
        }
    }

    document.querySelectorAll('table.table').forEach(preparerTableau);
})();
