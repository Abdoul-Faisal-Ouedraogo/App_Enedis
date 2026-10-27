import datetime as dt
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CLIMATE_ZONES_PATH = BASE_DIR / "data" / "climate_zones.csv"
CITY_PATH = BASE_DIR / "data" / "communes-france-2025.csv"


class DataCleaner:
    """Class to handle all the procedure for data cleaning and transformation from raw data coming from Ademe API."""

    def __init__(self, dataframe: pd.DataFrame):
        # Read the file for mapping.
        df_zones = pd.read_csv(CLIMATE_ZONES_PATH, dtype={"Departement": str})

        # Create a dict: department -> zone
        self.climate_zones = pd.Series(
            df_zones["Zone climatique"].values, index=df_zones["Departement"]
        ).to_dict()

        self.cities = pd.read_csv(
            CITY_PATH, dtype={"code_insee": str, "dep_code": str}, low_memory=False
        )

        # Groupby department and take the mean altitude to average altitudes per department.
        self.departments = self.cities.groupby("dep_code")["altitude_moyenne"].mean()

        # Isolate the merging columns for the cities.
        self.cities = self.cities[["code_insee", "altitude_moyenne"]]

        self.df = dataframe

    def select_relevant_variables(self) -> pd.DataFrame:
        """Select relevant variables for the analysis."""

        relevant_columns = [
            "cout_total_5_usages",
            "cout_chauffage",
            "cout_eclairage",
            "cout_refroidissement",
            "cout_auxiliaires",
            "cout_ecs",
            "conso_5_usages_ef",
            "conso_chauffage_ef",
            "conso_eclairage_ef",
            "conso_auxiliaires_ef",
            "conso_ecs_ef",
            "conso_refroidissement_ef",
            "surface_habitable_logement",
            "nombre_niveau_logement",
            "type_batiment",
            "annee_construction",
            "code_insee_ban",
            "code_departement_ban",
            "etiquette_dpe",
            "etiquette_ges",
            "nom_commune_ban",
            "code_postal_ban",
            "emission_ges_chauffage",
            "emission_ges_eclairage",
            "emission_ges_ecs",
            "emission_ges_5_usages",
            "emission_ges_auxiliaires",
            "emission_ges_refroidissement",
            "_geopoint",
            "type_energie_principale_chauffage",
            "age_batiment",
            "date_reception_dpe",
            "numero_dpe",
        ]

        self.df = self.df.loc[:, relevant_columns]
        return self.df

    def add_construction_year(self) -> pd.DataFrame:
        """Add a new column "annee_construction" if missing (from the new housing dataset), filled with the current year."""

        current_year = dt.datetime.now().year

        # Check if the column is missing.
        if "annee_construction" not in self.df.columns:
            # Add the year column if missing values.
            self.df["annee_construction"] = current_year

        # Set missing values to median year of construction.
        self.df.loc[:, "annee_construction"] = self.df["annee_construction"].fillna(
            self.df["annee_construction"].median()
        )

        # Convert to integer if needed.
        self.df["annee_construction"] = self.df["annee_construction"].astype(int)

        # Create the age column.
        self.df["age_batiment"] = current_year - self.df["annee_construction"]

        return self.df

    def cost_cleaning(self) -> pd.DataFrame:
        """Clean the "cout_total_5_usages" column."""

        self.df = self.df.dropna(subset=["cout_total_5_usages"])

        # Use the IQR method to remove outliers.
        Q1 = self.df["cout_total_5_usages"].quantile(0.25)
        Q3 = self.df["cout_total_5_usages"].quantile(0.75)
        IQR = Q3 - Q1

        # Filtering the dataframe
        self.df = self.df[
            (self.df["cout_total_5_usages"] >= Q1 - 1.5 * IQR)
            & (self.df["cout_total_5_usages"] <= Q3 + 1.5 * IQR)
        ]

        return self.df

    def energie_type_cleaning(self) -> pd.DataFrame:
        """Clean the "type_energie_principale_chauffage" column."""

        # Major classes:
        energie_types = ["Gaz naturel", "Électricité"]

        # Replacing all the minor modalities into one single "Autre" modality.
        self.df.loc[
            ~self.df["type_energie_principale_chauffage"].isin(energie_types),
            "type_energie_principale_chauffage",
        ] = "Autre"

        return self.df

    def surface_cleaning(self) -> pd.DataFrame:
        """Clean the "surface_habitable_logement" column."""

        # Using interquartile method to eliminate outliers (and missing values).
        Q1 = self.df["surface_habitable_logement"].quantile(0.25)
        Q3 = self.df["surface_habitable_logement"].quantile(0.75)
        IQR = Q3 - Q1

        # Filtering the dataframe
        self.df = self.df[
            (self.df["surface_habitable_logement"] >= Q1 - 1.5 * IQR)
            & (self.df["surface_habitable_logement"] <= Q3 + 1.5 * IQR)
        ]

        return self.df

    def level_cleaning(self) -> pd.DataFrame:
        """Clean the "nombre_niveau_logement" column."""

        # Discard missing values.
        self.df.loc[:, "nombre_niveau_logement"].dropna(inplace=True)
        # Discard outliers.
        self.df = self.df[
            (self.df["nombre_niveau_logement"] >= 1)
            & (self.df["nombre_niveau_logement"] <= 10)
        ]

        return self.df

    def insee_code_cleaning(self) -> pd.DataFrame:
        """Clean the "code_insee_ban" column."""

        # Changing code_insee for string.
        self.df["code_insee_ban"] = self.df["code_insee_ban"].astype(str)

        # Adding a 0 to the insee code being too short.
        self.df["code_insee_ban"] = self.df["code_insee_ban"].apply(
            lambda x: x.zfill(5)
        )

        return self.df

    def clean_department_code(self) -> pd.DataFrame:
        """Clean the 'code_departement_ban' column to ensure it's a two-character string."""
        self.df["code_departement_ban"] = self.df["code_departement_ban"].astype(str)
        self.df["code_departement_ban"] = self.df["code_departement_ban"].apply(
            lambda x: x.zfill(2)
        )

        return self.df

    def split_coordinates(self) -> pd.DataFrame:
        """Split the '_geopoint' column into 'lat' and 'lon' columns before dropping it."""
        self.df[["lat", "lon"]] = (
            self.df["_geopoint"].str.split(",", expand=True).astype(float)
        )
        self.df.drop(columns=["_geopoint"], inplace=True)

        return self.df

    def map_climate_zones(self) -> pd.DataFrame:
        """Map climate zones to the dataframe based on department codes."""
        self.df["zone_climatique"] = self.df["code_departement_ban"].map(
            self.climate_zones
        )

        return self.df

    def extract_altitude(self) -> pd.DataFrame:
        """Extract altitude information from the cities dataset based on INSEE codes."""

        # Use the insee code to determine the altitude.
        self.df = self.df.merge(
            self.cities, left_on="code_insee_ban", right_on="code_insee", how="left"
        )

        # Completing missing altitude by averaging per department.
        missing = self.df[self.df["altitude_moyenne"].isna()].drop(
            columns=["altitude_moyenne"]
        )

        missing = missing.merge(
            self.departments,
            left_on="code_departement_ban",
            right_index=True,
            how="left",
        )

        self.df.loc[missing.index, "altitude_moyenne"] = missing["altitude_moyenne"]

        return self.df

    def clean_all(self) -> pd.DataFrame:
        """Run all cleaning methods in sequence."""
        self.add_construction_year()
        self.select_relevant_variables()
        self.cost_cleaning()
        self.energie_type_cleaning()
        self.surface_cleaning()
        self.level_cleaning()
        self.insee_code_cleaning()
        self.clean_department_code()
        self.split_coordinates()
        self.map_climate_zones()
        self.extract_altitude()

        return self.df
