/*
 * Panneau accessibilité (cf. templates/partials/panneau_accessibilite.html).
 * Applique plusieurs réglages indépendants sur <html>, et propose une
 * lecture à voix haute du contenu principal via la synthèse vocale du
 * navigateur (Web Speech API).
 *
 * Mémorisation des réglages :
 * - compte connecté : enregistrés côté serveur (PreferenceAccessibilite, via
 *   l'URL accueil:preferences_accessibilite) pour être réappliqués à chaque
 *   connexion sur n'importe quel navigateur — déjà rendus directement sur
 *   <html> par templates/base.html (cf. Projet_veto/context_processors.py),
 *   donc pas de script de préchargement à faire ici dans ce cas ;
 * - visiteur non connecté : mémorisés uniquement dans le navigateur courant
 *   (localStorage), pré-appliqués par un petit script inline avant le
 *   premier rendu (cf. accueil/templates/accueil/*.html et
 *   registration/login.html).
 */
(function () {
    'use strict';

    var CLES = {
        taille: 'a11yTaille',
        contraste: 'a11yContraste',
        police: 'a11yPolice',
        animations: 'a11yReduireAnimations',
        palette: 'a11yPaletteDaltonisme',
        sombre: 'a11yModeSombre',
    };

    var CLASSE_PAR_CLE = {
        contraste: 'a11y-contraste',
        police: 'a11y-police-lisible',
        animations: 'a11y-reduire-animations',
        palette: 'a11y-palette-daltonisme',
    };

    var CHAMP_PAR_CLE = {
        contraste: 'contraste_eleve',
        police: 'police_lisible',
        animations: 'reduire_animations',
        palette: 'palette_daltonisme',
    };

    function ecrireLocal(cle, valeur) {
        try {
            localStorage.setItem(cle, valeur);
        } catch (e) {
            // Stockage indisponible (navigation privée, quota...) : le réglage
            // reste effectif pour la page en cours, simplement non mémorisé.
        }
    }

    function appliquerTaille(valeur) {
        var html = document.documentElement;
        html.classList.remove('a11y-taille-grand', 'a11y-taille-tres-grand');
        if (valeur === 'grand') { html.classList.add('a11y-taille-grand'); }
        if (valeur === 'tres-grand') { html.classList.add('a11y-taille-tres-grand'); }
    }

    function initPanneau() {
        var conteneur = document.getElementById('panneauAccessibilite');
        var groupeTaille = document.querySelectorAll('[data-a11y-taille]');
        var caseContraste = document.getElementById('a11yContraste');
        var casePolice = document.getElementById('a11yPoliceLisible');
        var caseAnimations = document.getElementById('a11yReduireAnimations');
        var casePalette = document.getElementById('a11yPaletteDaltonisme');
        var caseModeSombre = document.getElementById('a11yModeSombre');
        var boutonLecture = document.getElementById('a11yLireVoixHaute');

        if (!conteneur) {
            return; // Page sans panneau accessibilité (ne devrait pas arriver).
        }

        var html = document.documentElement;
        var authentifie = conteneur.getAttribute('data-authentifie') === '1';
        var urlMaj = conteneur.getAttribute('data-url-maj');

        function enregistrerSurLeServeur(champ, valeur) {
            var jeton = conteneur.querySelector('input[name=csrfmiddlewaretoken]');
            if (!urlMaj || !jeton) { return; }
            fetch(urlMaj, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': jeton.value,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: 'champ=' + encodeURIComponent(champ) + '&valeur=' + encodeURIComponent(valeur),
            }).catch(function () {
                // Hors-ligne ou erreur serveur : le réglage reste appliqué pour
                // la page en cours, simplement pas (encore) enregistré sur le
                // compte. Sans conséquence grave, on ne bloque pas l'interface.
            });
        }

        // Compte connecté : enregistre sur le compte (persistant, tous
        // navigateurs). Visiteur non connecté : mémorise dans ce navigateur
        // seulement (localStorage), comme avant.
        function persister(cleLocalStorage, champServeur, valeur) {
            if (authentifie) {
                enregistrerSurLeServeur(champServeur, valeur);
            } else {
                ecrireLocal(cleLocalStorage, valeur);
            }
        }

        var tailleActuelle = authentifie
            ? (html.classList.contains('a11y-taille-tres-grand') ? 'tres-grand'
                : html.classList.contains('a11y-taille-grand') ? 'grand' : 'normal')
            : (localStorage.getItem(CLES.taille) || 'normal');

        // --- Synchronise l'état des contrôles avec les classes déjà en place ---
        groupeTaille.forEach(function (bouton) {
            var actif = bouton.getAttribute('data-a11y-taille') === tailleActuelle;
            bouton.classList.toggle('active', actif);
            bouton.setAttribute('aria-pressed', actif ? 'true' : 'false');
            bouton.addEventListener('click', function () {
                var valeur = bouton.getAttribute('data-a11y-taille');
                appliquerTaille(valeur);
                persister(CLES.taille, 'taille_texte', valeur);
                groupeTaille.forEach(function (b) {
                    var estCelui = b === bouton;
                    b.classList.toggle('active', estCelui);
                    b.setAttribute('aria-pressed', estCelui ? 'true' : 'false');
                });
            });
        });

        function brancherCase(caseACocher, cle) {
            if (!caseACocher) { return; }
            var classe = CLASSE_PAR_CLE[cle];
            var champServeur = CHAMP_PAR_CLE[cle];
            caseACocher.checked = html.classList.contains(classe);
            caseACocher.addEventListener('change', function () {
                html.classList.toggle(classe, caseACocher.checked);
                persister(CLES[cle], champServeur, caseACocher.checked ? '1' : '0');
            });
        }

        brancherCase(caseContraste, 'contraste');
        brancherCase(casePolice, 'police');
        brancherCase(caseAnimations, 'animations');
        brancherCase(casePalette, 'palette');

        // Le mode sombre n'est pas une classe mais l'attribut data-bs-theme
        // (thème sombre natif de Bootstrap 5.3, cf. static/css/style.css).
        if (caseModeSombre) {
            caseModeSombre.checked = html.getAttribute('data-bs-theme') === 'dark';
            caseModeSombre.addEventListener('change', function () {
                if (caseModeSombre.checked) {
                    html.setAttribute('data-bs-theme', 'dark');
                } else {
                    html.removeAttribute('data-bs-theme');
                }
                persister(CLES.sombre, 'mode_sombre', caseModeSombre.checked ? '1' : '0');
            });
        }

        // --- Lecture à voix haute du contenu principal ---
        if (boutonLecture) {
            initLectureVoixHaute(boutonLecture);
        }
    }

    function initLectureVoixHaute(bouton) {
        if (!('speechSynthesis' in window)) {
            bouton.disabled = true;
            bouton.title = "La lecture à voix haute n'est pas prise en charge par ce navigateur.";
            return;
        }

        var synthese = window.speechSynthesis;
        var enCours = false;

        function texteLisible(zone) {
            // Ignore les zones techniques (scripts, boutons du panneau lui-même)
            // pour ne lire que le contenu réellement utile.
            var clone = zone.cloneNode(true);
            var panneaux = clone.querySelectorAll('script, style, .dropdown-menu');
            panneaux.forEach(function (el) { el.remove(); });
            return clone.textContent.replace(/\s+/g, ' ').trim();
        }

        function arreter() {
            synthese.cancel();
            enCours = false;
            bouton.innerHTML = '<i class="bi bi-volume-up" aria-hidden="true"></i> Lire cette page à voix haute';
        }

        bouton.addEventListener('click', function () {
            if (enCours) {
                arreter();
                return;
            }

            var zone = document.getElementById('contenu-principal') || document.body;
            var texte = texteLisible(zone);
            if (!texte) { return; }

            var enonce = new SpeechSynthesisUtterance(texte);
            enonce.lang = 'fr-FR';
            enonce.onend = arreter;
            enonce.onerror = arreter;

            synthese.cancel(); // Coupe une éventuelle lecture précédente.
            synthese.speak(enonce);
            enCours = true;
            bouton.innerHTML = '<i class="bi bi-stop-circle" aria-hidden="true"></i> Arrêter la lecture';
        });

        // Une navigation vers une autre page doit couper la synthèse en cours.
        window.addEventListener('beforeunload', function () {
            synthese.cancel();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPanneau);
    } else {
        initPanneau();
    }
})();
