/*
 * Lecture à voix haute du contenu principal de la page, par la synthèse
 * vocale du navigateur (Web Speech API) : bouton « Lire cette page à voix
 * haute » du panneau accessibilité (templates/partials/panneau_accessibilite.html).
 *
 * C'est le seul script propre à l'application : la synthèse vocale n'existe
 * que dans le navigateur, le serveur ne peut pas la piloter. Tout le reste de
 * l'interface — y compris les autres réglages du panneau — passe par htmx
 * (cf. CLAUDE.md).
 */
(function () {
    'use strict';

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

    function init() {
        var bouton = document.getElementById('a11yLireVoixHaute');
        if (bouton) {
            initLectureVoixHaute(bouton);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
