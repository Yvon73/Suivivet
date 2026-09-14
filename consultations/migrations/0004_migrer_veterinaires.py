# Reprend l'ancien champ Consultation.veterinaire (un nom en texte libre)
# vers une fiche Veterinaire (migration 0002), en dédupliquant par nom : deux
# consultations partageant le même nom de vétérinaire pointent désormais vers
# la même fiche (coordonnées à compléter ensuite via la fiche vétérinaire).
from django.db import migrations


def migrer_vers_veterinaire(apps, schema_editor):
    Consultation = apps.get_model('consultations', 'Consultation')
    Veterinaire = apps.get_model('consultations', 'Veterinaire')

    veterinaires_par_nom = {}
    for consultation in Consultation.objects.all():
        nom = (consultation.veterinaire or 'Inconnu').strip() or 'Inconnu'
        cle = nom.lower()
        veterinaire = veterinaires_par_nom.get(cle)
        if veterinaire is None:
            veterinaire = Veterinaire.objects.filter(nom__iexact=nom).first()
        if veterinaire is None:
            veterinaire = Veterinaire.objects.create(nom=nom)
        veterinaires_par_nom[cle] = veterinaire
        consultation.veterinaire_fk = veterinaire
        consultation.save(update_fields=['veterinaire_fk'])


def revenir_vers_nom(apps, schema_editor):
    Consultation = apps.get_model('consultations', 'Consultation')
    for consultation in Consultation.objects.all():
        if consultation.veterinaire_fk_id:
            consultation.veterinaire = consultation.veterinaire_fk.nom
            consultation.save(update_fields=['veterinaire'])


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0003_consultation_veterinaire_fk'),
    ]

    operations = [
        migrations.RunPython(migrer_vers_veterinaire, revenir_vers_nom),
    ]
