"""Live-model regression tests for the scoring prompt's judgment quality --
not just plumbing. Mocked tests in test_scoring.py verify the code around
the model (truncation, recompute, mapping); they can never catch a judgment
bug because the fake client just echoes back whatever the test hard-codes.
This file calls the real GPT-4o model and checks its actual reasoning,
which is what caught the radios/рации false positive in the first place
(2026-07-23 live audit): a рации/walkie-talkie reseller's tender feed
scored a World Bank "20 local radio STATIONS" broadcast-media tender at 68%
("Рассмотреть") purely on the surface word "radio(s)".

Opt-in via RUN_LIVE_EVALS=1 -- real API calls, real cost, not for every
CI run.
"""
import os

import pytest

from app.scraping.scoring import extract_and_score

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_EVALS") != "1",
    reason="live-model eval -- set RUN_LIVE_EVALS=1 to run (costs real API calls)",
)

RACII_PROFILE = (
    "Компания предоставляет услуги аутстаффинга во всех отраслях в Узбекистане и "
    "открыта для работы с любыми компаниями, независимо от их размера или сектора. "
    "Нет особых предпочтений по типам проектов. Также интересуются тендерами в "
    "области туризма и бизнес-ивентов в Узбекистане. Компания занимается продажей "
    "профессиональных и любительских раций и заинтересована в тендерах, связанных с "
    "покупкой раций для компаний в Узбекистане."
)

WORLD_BANK_RADIO_STATIONS_CONTENT = """
Procurement Notice
World Bank Group
Project: PRSEB (Projet de Renforcement du Systeme Educatif au Burkina Faso)
Notice Title: SELECTION DE 20 RADIOS DE PROXIMITE POUR LA COMMUNICATION ET LA
VISIBILITE RELATIVES AUX REFORMES DU MENAET MISES EN OEUVRE PAR LE PRSEB
Country: Burkina Faso
Deadline: 21.07.2026
Description: Le Ministere de l'Education Nationale, de l'Alphabetisation et de
la Promotion des Langues Nationales (MENAET), a travers le PRSEB, souhaite
selectionner 20 stations de radio de proximite (radios communautaires locales
diffusant en FM) pour produire et diffuser des emissions de sensibilisation du
public sur les reformes du secteur educatif. Les radios selectionnees devront
disposer d'une couverture geographique locale, d'une equipe de journalistes et
d'une grille de programmes existante. Il ne s'agit pas de la fourniture
d'equipements radio mais de prestations de services de diffusion mediatique.
"""

SEVENTEAM_PROFILE = (
    "Компания: Seventeam (seventeam.uz), Ташкент, Узбекистан. Сфера деятельности: "
    "MICE-агентство и Destination Management Company (DMC) полного цикла. "
    "Организуем деловые и корпоративные мероприятия под ключ — конференции, "
    "форумы, выставки, деловые встречи, инсентив-туры, деловые поездки и делегации."
)

UZTENDER_FOREIGN_TRIP_CONTENT = """
Тендер: ПРОДЛЕНИЕ: Организация зарубежных поездок
Заказчик: Проект «Укрепление статистической системы Узбекистана»
Срок подачи: 30.07.2026
Описание: Требуется организация деловых зарубежных поездок (авиабилеты,
визовая поддержка, бронирование отелей, трансфер) для сотрудников проекта в
рамках международных стажировок и конференций по статистике. Организатор
должен иметь опыт организации бизнес-поездок и деловых мероприятий.
"""


def test_does_not_match_radio_stations_tender_to_two_way_radio_reseller():
    """The exact false positive found in the 2026-07-23 live audit: GPT-4o
    matched a рации (two-way radio hardware) reseller to a World Bank tender
    selecting FM broadcast stations, purely because both mention "radio"."""
    result = extract_and_score(
        WORLD_BANK_RADIO_STATIONS_CONTENT,
        {"name": "World Bank", "url": "https://projects.worldbank.org/en/projects-operations/procurement-detail/OP00454733"},
        RACII_PROFILE,
    )
    assert result, "expected the tender to be extracted"
    tender = result[0]
    assert tender["matchPercent"] < 40, (
        f"radio-STATIONS tender should not score as a match for a two-way-radio-HARDWARE "
        f"reseller, got {tender['matchPercent']}: {tender.get('whyParticipate')}"
    )
    assert tender["recommendation"] == "Пропустить"


def test_still_matches_genuinely_relevant_foreign_trip_tender():
    """Control case: the fix must not just suppress every score indiscriminately --
    a real match (foreign-trip organization for a MICE/DMC agency) must stay high."""
    result = extract_and_score(
        UZTENDER_FOREIGN_TRIP_CONTENT,
        {"name": "uztender.com", "url": "https://uztender.com/example"},
        SEVENTEAM_PROFILE,
    )
    assert result, "expected the tender to be extracted"
    tender = result[0]
    assert tender["matchPercent"] >= 70, (
        f"a genuine service-match (foreign-trip organization for a MICE/DMC agency) "
        f"should still score high, got {tender['matchPercent']}: {tender.get('whyParticipate')}"
    )
    assert tender["recommendation"] == "Подать заявку"
