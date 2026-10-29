"""Traçabilité locale des DPE ; ces colonnes ne sont jamais des variables ML."""
RAW_FIELDS = [
    "numero_dpe", "numero_dpe_remplace", "date_reception_dpe",
    "date_etablissement_dpe", "date_visite_diagnostiqueur",
    "identifiant_ban", "numero_dpe_immeuble_associe",
]
LINEAGE_FIELDS = ["_source_dataset", "_source_row"] + RAW_FIELDS
