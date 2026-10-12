"""Ménage des fichiers téléversés (FileField).

Django ne supprime jamais du disque le fichier d'un FileField : ni quand la
ligne est supprimée, ni quand le fichier est remplacé. Sans ce module, un
document ou une facture « supprimé » resterait indéfiniment dans media/ (et
dans les sauvegardes), sans plus aucun moyen de l'effacer depuis l'application.
"""
from django.db import transaction


def supprimer_fichier_orphelin(modele, champ, nom):
    """Supprime du stockage le fichier `nom` du champ `champ` de `modele`,
    une fois la transaction en cours validée (si elle est annulée, la ligne
    existe toujours et son fichier doit rester) et seulement si plus aucune
    ligne ne le référence."""
    if not nom:
        return

    def _supprimer():
        if not modele._default_manager.filter(**{champ: nom}).exists():
            modele._meta.get_field(champ).storage.delete(nom)

    transaction.on_commit(_supprimer)


def brancher_menage_fichier(modele, champ):
    """Branche le ménage du FileField `champ` de `modele` : à la suppression
    de la ligne (signal post_delete, donc aussi lors d'une suppression en
    cascade ou par QuerySet.delete()) et au remplacement du fichier (ancien
    nom relu en base avant l'enregistrement, comparé après)."""
    from django.db.models.signals import post_delete, post_save, pre_save

    attribut = f'_ancien_{champ}'

    def avant_enregistrement(sender, instance, **kwargs):
        ancien = None
        if instance.pk:
            ancien = sender._default_manager.filter(pk=instance.pk).values_list(champ, flat=True).first()
        setattr(instance, attribut, ancien)

    def apres_enregistrement(sender, instance, **kwargs):
        ancien = getattr(instance, attribut, None)
        if ancien and ancien != getattr(instance, champ).name:
            supprimer_fichier_orphelin(sender, champ, ancien)

    def apres_suppression(sender, instance, **kwargs):
        supprimer_fichier_orphelin(sender, champ, getattr(instance, champ).name)

    # weak=False : ces fonctions locales ne sont référencées nulle part ailleurs.
    uid = f'menage_{modele._meta.label_lower}_{champ}'
    pre_save.connect(avant_enregistrement, sender=modele, weak=False, dispatch_uid=f'{uid}_pre_save')
    post_save.connect(apres_enregistrement, sender=modele, weak=False, dispatch_uid=f'{uid}_post_save')
    post_delete.connect(apres_suppression, sender=modele, weak=False, dispatch_uid=f'{uid}_post_delete')
