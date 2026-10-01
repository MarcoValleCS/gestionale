"""Test di dipendenti, registrazione ore, ferie e registro presenze."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.accounts.permissions import ROLE_ADMIN, ROLE_HR  # noqa: F401
from apps.contacts.models import Contact
from apps.core.models import TimeStampedModel  # noqa: F401  (verifica import di base)
from apps.jobs.models import Job  # noqa: F401  (usato nei test dei collaboratori)

from .models import Collaborator, CollaboratorTimeEntry, Employee, LeaveRequest, TimeEntry, working_days

User = get_user_model()


class HrTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")
        cls.plain = User.objects.create_user("operaio", "operaio@example.com", "password123!")
        cls.hr_user = User.objects.create_user("ufficio", "ufficio@example.com", "password123!")
        cls.hr_user.groups.add(Group.objects.get(name="Personale"))

        cls.employee = Employee.objects.create(
            first_name="Luca",
            last_name="Bianchi",
            qualification="Idraulico",
            hired_on=date(2024, 3, 1),
            hourly_cost=Decimal("22.50"),
            holiday_days_per_year=Decimal("26"),
            rol_hours_per_year=Decimal("40"),
        )
        cls.other = Employee.objects.create(first_name="Sara", last_name="Rossi", qualification="Ufficio")

    def login(self, user=None):
        self.client.force_login(user or self.admin)


class EmployeeModelTest(HrTestBase):
    def test_codice_generato_automaticamente(self):
        self.assertTrue(self.employee.code.startswith("DIP"))
        self.assertEqual(len(self.employee.code), 8)

    def test_codici_diversi(self):
        self.assertNotEqual(self.employee.code, self.other.code)

    def test_nome_completo(self):
        self.assertEqual(self.employee.full_name, "Bianchi Luca")

    def test_dipendente_in_corso(self):
        self.assertTrue(self.employee.is_current)

    def test_dipendente_cessato(self):
        self.employee.active = False
        self.assertFalse(self.employee.is_current)

    def test_cessazione_futura_resta_in_corso(self):
        self.employee.terminated_on = date(2099, 1, 1)
        self.assertTrue(self.employee.is_current)


class WorkingDaysTest(TestCase):
    def test_settimana_intera(self):
        # lunedì 5 → venerdì 9 ottobre 2026
        self.assertEqual(working_days(date(2026, 10, 5), date(2026, 10, 9)), 5)

    def test_weekend_escluso(self):
        # sabato 3 → domenica 4 ottobre 2026
        self.assertEqual(working_days(date(2026, 10, 3), date(2026, 10, 4)), 0)

    def test_intervallo_su_due_settimane(self):
        # venerdì 2 → lunedì 5 ottobre 2026 = ven, lun
        self.assertEqual(working_days(date(2026, 10, 2), date(2026, 10, 5)), 2)

    def test_intervallo_rovesciato(self):
        self.assertEqual(working_days(date(2026, 10, 9), date(2026, 10, 5)), 0)

    def test_stesso_giorno_lavorativo(self):
        self.assertEqual(working_days(date(2026, 10, 5), date(2026, 10, 5)), 1)


class TimeEntryTest(HrTestBase):
    def test_registrazione_ore_e_totale(self):
        TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"))
        TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 6), hours=Decimal("7.5"))
        self.assertEqual(self.employee.hours_in_month(2026, 10), Decimal("15.5"))

    def test_totale_filtrato_per_tipo(self):
        TimeEntry.objects.create(
            employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"), kind=TimeEntry.KIND_ORDINARY
        )
        TimeEntry.objects.create(
            employee=self.employee, date=date(2026, 10, 5), hours=Decimal("2"), kind=TimeEntry.KIND_OVERTIME
        )
        self.assertEqual(
            self.employee.hours_between(date(2026, 10, 1), date(2026, 10, 31), TimeEntry.KIND_OVERTIME),
            Decimal("2"),
        )

    def test_ore_solo_del_dipendente(self):
        TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"))
        TimeEntry.objects.create(employee=self.other, date=date(2026, 10, 5), hours=Decimal("4"))
        self.assertEqual(self.employee.hours_in_month(2026, 10), Decimal("8"))

    def test_costo_calcolato(self):
        entry = TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"))
        self.assertEqual(entry.cost, Decimal("180.00"))

    def test_costo_assente_senza_tariffa(self):
        entry = TimeEntry.objects.create(employee=self.other, date=date(2026, 10, 5), hours=Decimal("8"))
        self.assertIsNone(entry.cost)


class LeaveModelTest(HrTestBase):
    def test_giorni_lavorativi_ferie(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )
        self.assertEqual(leave.days, 5)
        self.assertEqual(leave.duration_label, "5 giorni")

    def test_permesso_orario_non_conta_giorni(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_ROL,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
            hours=Decimal("2"),
        )
        self.assertEqual(leave.days, 0)
        self.assertEqual(leave.duration_label, "2 h")

    def test_saldo_ferie_dopo_approvazione(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )
        # non ancora approvata: il residuo non cambia
        self.assertEqual(self.employee.holiday_balance(2026), Decimal("26"))
        leave.approve(self.admin)
        self.assertEqual(self.employee.leave_used(2026, LeaveRequest.KIND_HOLIDAY), Decimal("5"))
        self.assertEqual(self.employee.holiday_balance(2026), Decimal("21"))

    def test_saldo_permessi_in_ore(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_ROL,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
            hours=Decimal("3"),
        )
        leave.approve(self.admin)
        self.assertEqual(self.employee.rol_balance(2026), Decimal("37"))

    def test_ferie_a_cavallo_di_due_anni_conta_solo_l_anno(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 12, 30),
            end_date=date(2027, 1, 5),
        )
        leave.approve(self.admin)
        # 30 e 31 dicembre 2026 (mer e gio) = 2 giorni nel 2026
        self.assertEqual(self.employee.leave_used(2026, LeaveRequest.KIND_HOLIDAY), Decimal("2"))

    def test_malattia_non_scala_le_ferie(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_SICK,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 6),
        )
        leave.approve(self.admin)
        self.assertEqual(self.employee.holiday_balance(2026), Decimal("26"))
        self.assertEqual(self.employee.leave_used(2026, LeaveRequest.KIND_SICK), Decimal("2"))

    def test_rifiuto_non_scala(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )
        leave.reject(self.admin)
        self.assertEqual(self.employee.holiday_balance(2026), Decimal("26"))

    def test_approvazione_registra_chi_e_quando(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
        )
        leave.approve(self.admin)
        self.assertEqual(leave.approved_by, self.admin)
        self.assertIsNotNone(leave.approved_at)


class HrViewTest(HrTestBase):
    def test_elenco_dipendenti(self):
        self.login()
        response = self.client.get(reverse("hr:employee_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bianchi Luca")

    def test_scheda_dipendente_con_saldi(self):
        self.login()
        response = self.client.get(reverse("hr:employee_detail", args=[self.employee.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["holiday_balance"], Decimal("26"))

    def test_registro_presenze_mostra_ore(self):
        self.login()
        TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"))
        response = self.client.get(reverse("hr:timesheet"), {"anno": 2026, "mese": 10})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["grand_total"], Decimal("8"))

    def test_registro_presenze_mostra_sigla_ferie(self):
        self.login()
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
        )
        leave.approve(self.admin)
        response = self.client.get(reverse("hr:timesheet"), {"anno": 2026, "mese": 10})
        marks = [cell["leave"] for row in response.context["rows"] for cell in row["cells"]]
        self.assertIn("F", marks)

    def test_elenco_assenze(self):
        self.login()
        response = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(response.status_code, 200)

    def test_utente_senza_ruolo_non_puo_creare_dipendente(self):
        self.login(self.plain)
        response = self.client.get(reverse("hr:employee_create"))
        self.assertEqual(response.status_code, 403)

    def test_ruolo_personale_puo_creare_dipendente(self):
        self.login(self.hr_user)
        response = self.client.get(reverse("hr:employee_create"))
        self.assertEqual(response.status_code, 200)

    def test_creazione_dipendente_da_form(self):
        self.login()
        response = self.client.post(
            reverse("hr:employee_create"),
            {
                "first_name": "Marco",
                "last_name": "Verdi",
                "fiscal_code": "",
                "email": "",
                "phone": "",
                "qualification": "Elettricista",
                "hired_on": "",
                "terminated_on": "",
                "contract_weekly_hours": "40",
                "hourly_cost": "",
                "holiday_days_per_year": "26",
                "rol_hours_per_year": "0",
                "active": "on",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(last_name="Verdi").exists())

    def test_cessazione_prima_di_assunzione_rifiutata(self):
        self.login()
        response = self.client.post(
            reverse("hr:employee_update", args=[self.employee.pk]),
            {
                "first_name": "Luca",
                "last_name": "Bianchi",
                "hired_on": "2026-05-01",
                "terminated_on": "2026-01-01",
                "contract_weekly_hours": "40",
                "holiday_days_per_year": "26",
                "rol_hours_per_year": "40",
                "active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "terminated_on", "La data di cessazione non può precedere quella di assunzione.")

    def test_ore_maggiori_di_24_rifiutate(self):
        self.login()
        response = self.client.post(
            reverse("hr:timeentry_create"),
            {
                "employee": self.employee.pk,
                "date": "2026-10-05",
                "hours": "30",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "hours", "Non puoi registrare più di 24 ore in un giorno.")

    def test_permesso_orario_su_piu_giorni_rifiutato(self):
        self.login()
        response = self.client.post(
            reverse("hr:leave_create"),
            {
                "employee": self.employee.pk,
                "kind": LeaveRequest.KIND_ROL,
                "start_date": "2026-10-05",
                "end_date": "2026-10-07",
                "hours": "2",
                "reason": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("hours", response.context["form"].errors)


class BulkTimeEntryTest(HrTestBase):
    def test_crea_una_registrazione_per_dipendente(self):
        self.login()
        response = self.client.post(
            reverse("hr:timeentry_bulk"),
            {
                "date": "2026-10-05",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "Montaggio",
                f"hours_{self.employee.pk}": "8",
                f"hours_{self.other.pk}": "6.5",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TimeEntry.objects.count(), 2)
        self.assertEqual(TimeEntry.objects.get(employee=self.other).hours, Decimal("6.5"))

    def test_righe_vuote_ignorate(self):
        self.login()
        self.client.post(
            reverse("hr:timeentry_bulk"),
            {
                "date": "2026-10-05",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
                f"hours_{self.employee.pk}": "8",
                f"hours_{self.other.pk}": "",
            },
        )
        self.assertEqual(TimeEntry.objects.count(), 1)

    def test_secondo_salvataggio_aggiorna_invece_di_duplicare(self):
        self.login()
        payload = {
            "date": "2026-10-05",
            "kind": TimeEntry.KIND_ORDINARY,
            "job": "",
            "description": "",
            f"hours_{self.employee.pk}": "8",
            f"hours_{self.other.pk}": "",
        }
        self.client.post(reverse("hr:timeentry_bulk"), payload)
        payload[f"hours_{self.employee.pk}"] = "5"
        self.client.post(reverse("hr:timeentry_bulk"), payload)
        self.assertEqual(TimeEntry.objects.count(), 1)
        self.assertEqual(TimeEntry.objects.get().hours, Decimal("5"))

    def test_nessuna_ora_indicata_da_errore(self):
        self.login()
        response = self.client.post(
            reverse("hr:timeentry_bulk"),
            {
                "date": "2026-10-05",
                "kind": TimeEntry.KIND_ORDINARY,
                "job": "",
                "description": "",
                f"hours_{self.employee.pk}": "",
                f"hours_{self.other.pk}": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())


class LeaveWorkflowViewTest(HrTestBase):
    def test_approvazione_da_elenco(self):
        self.login()
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )
        response = self.client.post(reverse("hr:leave_approve", args=[leave.pk]))
        self.assertEqual(response.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_APPROVED)

    def test_rifiuto_da_elenco(self):
        self.login()
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 9),
        )
        self.client.post(reverse("hr:leave_reject", args=[leave.pk]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_REJECTED)

    def test_eliminazione_dipendente_rimuove_registrazioni(self):
        self.login()
        TimeEntry.objects.create(employee=self.employee, date=date(2026, 10, 5), hours=Decimal("8"))
        LeaveRequest.objects.create(
            employee=self.employee,
            kind=LeaveRequest.KIND_HOLIDAY,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 5),
        )
        response = self.client.post(reverse("hr:employee_delete", args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Employee.objects.filter(pk=self.employee.pk).exists())
        self.assertEqual(TimeEntry.objects.count(), 0)
        self.assertEqual(LeaveRequest.objects.count(), 0)


class CollaboratorTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Group

        from apps.jobs.models import Job

        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "password123!")

        # utente con il SOLO ruolo Collaboratore
        cls.collab_user = User.objects.create_user("scavatore", password="password123!")
        cls.collab_user.groups.add(Group.objects.get(name="Collaboratore"))

        # utente con il ruolo Collaboratore più un altro: non deve essere limitato
        cls.misto = User.objects.create_user("misto", password="password123!")
        cls.misto.groups.add(Group.objects.get(name="Collaboratore"))
        cls.misto.groups.add(Group.objects.get(name="Vendite"))

        # utente dell'ufficio che gestisce i collaboratori
        cls.ufficio = User.objects.create_user("ufficio", password="password123!")
        cls.ufficio.groups.add(Group.objects.get(name="Personale"))

        cls.cliente = Contact.objects.create(name="Cliente Piscina S.r.l.", is_customer=True)
        cls.collaboratore = Collaborator.objects.create(
            name="Mario Scavi", company="Scavi Bianchi", specialization="scavo", user=cls.collab_user
        )
        cls.collega = Collaborator.objects.create(name="Altro Collaboratore")
        cls.cantiere = Job.objects.create(name="Piscina Rossi", customer=cls.cliente)

    def login(self, utente=None):
        self.client.force_login(utente or self.admin)


class CollaboratorModelTest(CollaboratorTestBase):
    def test_codice_generato(self):
        self.assertTrue(self.collaboratore.code.startswith("COL"))

    def test_nome_con_ditta(self):
        self.assertEqual(str(self.collaboratore), "Mario Scavi (Scavi Bianchi)")

    def test_ore_per_mese_e_totali(self):
        CollaboratorTimeEntry.objects.create(collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2))
        CollaboratorTimeEntry.objects.create(collaborator=self.collaboratore, hours=Decimal("5.5"), date=date(2026, 3, 10))
        CollaboratorTimeEntry.objects.create(collaborator=self.collaboratore, hours=Decimal("4"), date=date(2026, 4, 1))
        self.assertEqual(self.collaboratore.hours_in_month(2026, 3), Decimal("13.5"))
        self.assertEqual(self.collaboratore.hours_total(), Decimal("17.5"))

    def test_compenso_calcolato(self):
        self.collaboratore.hourly_rate = Decimal("18.50")
        self.collaboratore.save(update_fields=["hourly_rate"])
        entry = CollaboratorTimeEntry.objects.create(
            collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2)
        )
        self.assertEqual(entry.amount, Decimal("148.00"))

    def test_compenso_assente_senza_tariffa(self):
        entry = CollaboratorTimeEntry.objects.create(
            collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2)
        )
        self.assertIsNone(entry.amount)


class CollaboratorAccessTest(CollaboratorTestBase):
    """Il collaboratore esterno non deve vedere niente oltre alla sua area."""

    def test_accede_alla_sua_area(self):
        self.login(self.collab_user)
        response = self.client.get(reverse("hr:collaborator_area"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mario Scavi")

    def test_non_accede_alle_altre_sezioni(self):
        self.login(self.collab_user)
        for url in (
            "/",
            reverse("catalog:product_list"),
            reverse("contacts:list"),
            reverse("sales:quote_list"),
            reverse("billing:salesinvoice_list"),
            reverse("hr:employee_list"),
            reverse("hr:timesheet"),
            reverse("inventory:stock_list"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302, f"{url} doveva rimandare all'area del collaboratore")
                self.assertIn("/personale/mio-lavoro/", response["Location"])

    def test_non_accede_alle_impostazioni(self):
        self.login(self.collab_user)
        response = self.client.get("/impostazioni/")
        self.assertEqual(response.status_code, 302)

    def test_chi_ha_anche_un_altro_ruolo_non_e_limitesato(self):
        self.login(self.misto)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get(reverse("sales:quote_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("hr:collaborator_area")).status_code, 200)

    def test_l_ufficio_non_e_limitesato(self):
        self.login(self.ufficio)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_utente_senza_collaboratore_collegato_vede_avviso(self):
        orfano = User.objects.create_user("orfano", password="password123!")
        orfano.groups.add(Group.objects.get(name="Collaboratore"))
        self.login(orfano)
        response = self.client.get(reverse("hr:collaborator_area"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "non è ancora collegato")


class CollaboratorTimeTest(CollaboratorTestBase):
    """Il collaboratore registra le proprie ore e non quelle degli altri."""

    def test_registra_le_ore(self):
        self.login(self.collab_user)
        response = self.client.post(
            reverse("hr:collaborator_entry_create"),
            {"date": "2026-03-02", "hours": "8", "job": self.cantiere.pk, "description": "Scavo vasca"},
        )
        self.assertEqual(response.status_code, 302)
        entry = CollaboratorTimeEntry.objects.get()
        self.assertEqual(entry.collaborator, self.collaboratore, "le ore devono finire sul collaboratore collegato")
        self.assertEqual(entry.hours, Decimal("8"))
        self.assertEqual(entry.job, self.cantiere)
        self.assertEqual(entry.created_by, self.collab_user)

    def test_non_puo_registrare_per_un_altro_collaboratore(self):
        """Anche forzando il campo, il collaboratore resta quello collegato all'utente."""
        self.login(self.collab_user)
        self.client.post(
            reverse("hr:collaborator_entry_create"),
            {
                "collaborator": self.collega.pk,
                "date": "2026-03-02",
                "hours": "8",
                "job": "",
                "description": "",
            },
        )
        entry = CollaboratorTimeEntry.objects.get()
        self.assertEqual(entry.collaborator, self.collaboratore)
        self.assertNotEqual(entry.collaborator, self.collega)

    def test_ore_oltre_24_rifiutate(self):
        self.login(self.collab_user)
        response = self.client.post(
            reverse("hr:collaborator_entry_create"),
            {"date": "2026-03-02", "hours": "30", "job": "", "description": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CollaboratorTimeEntry.objects.exists())

    def test_vede_solo_le_proprie_ore(self):
        CollaboratorTimeEntry.objects.create(collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2), description="Mie")
        CollaboratorTimeEntry.objects.create(collaborator=self.collega, hours=Decimal("8"), date=date(2026, 3, 3), description="Di un altro")
        self.login(self.collab_user)
        response = self.client.get(reverse("hr:collaborator_area"))
        self.assertContains(response, "Mie")
        self.assertNotContains(response, "Di un altro")

    def test_non_puo_modificare_le_ore_di_un_altro(self):
        altrui = CollaboratorTimeEntry.objects.create(
            collaborator=self.collega, hours=Decimal("8"), date=date(2026, 3, 3)
        )
        self.login(self.collab_user)
        response = self.client.get(reverse("hr:collaborator_entry_update", args=[altrui.pk]))
        self.assertEqual(response.status_code, 404)

    def test_non_puo_cancellare_le_ore_di_un_altro(self):
        altrui = CollaboratorTimeEntry.objects.create(
            collaborator=self.collega, hours=Decimal("8"), date=date(2026, 3, 3)
        )
        self.login(self.collab_user)
        self.client.post(reverse("hr:collaborator_entry_delete", args=[altrui.pk]))
        self.assertTrue(CollaboratorTimeEntry.objects.filter(pk=altrui.pk).exists())

    def test_puo_modificare_le_proprie(self):
        mia = CollaboratorTimeEntry.objects.create(
            collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2)
        )
        self.login(self.collab_user)
        response = self.client.post(
            reverse("hr:collaborator_entry_update", args=[mia.pk]),
            {"date": "2026-03-02", "hours": "6.5", "job": "", "description": "Corretto"},
        )
        self.assertEqual(response.status_code, 302)
        mia.refresh_from_db()
        self.assertEqual(mia.hours, Decimal("6.5"))

    def test_puo_cancellare_le_proprie(self):
        mia = CollaboratorTimeEntry.objects.create(
            collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2)
        )
        self.login(self.collab_user)
        self.client.post(reverse("hr:collaborator_entry_delete", args=[mia.pk]))
        self.assertFalse(CollaboratorTimeEntry.objects.filter(pk=mia.pk).exists())


class CollaboratorOfficeTest(CollaboratorTestBase):
    """Gestione dall'ufficio."""

    def test_elenco_collaboratori(self):
        self.login(self.ufficio)
        response = self.client.get(reverse("hr:collaborator_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mario Scavi")

    def test_crea_collaboratore(self):
        self.login(self.ufficio)
        response = self.client.post(
            reverse("hr:collaborator_create"),
            {
                "name": "Elettricista Verdi",
                "company": "Verdi Impianti",
                "specialization": "elettricista",
                "contact": "",
                "user": "",
                "fiscal_code": "",
                "phone": "",
                "email": "",
                "hourly_rate": "25.00",
                "active": "on",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collaborator.objects.filter(name="Elettricista Verdi").exists())

    def test_ufficio_vede_tutte_le_ore(self):
        CollaboratorTimeEntry.objects.create(collaborator=self.collaboratore, hours=Decimal("8"), date=date(2026, 3, 2))
        CollaboratorTimeEntry.objects.create(collaborator=self.collega, hours=Decimal("4"), date=date(2026, 3, 3))
        self.login(self.ufficio)
        response = self.client.get(reverse("hr:collaborator_time_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["entries"]), 2)
        self.assertEqual(response.context["filtered_total"], Decimal("12"))

    def test_ruolo_non_abilitato_non_gestisce_i_collaboratori(self):
        self.login(self.collab_user)
        response = self.client.get(reverse("hr:collaborator_list"))
        # il middleware lo rimanda alla sua area prima ancora del controllo sul ruolo
        self.assertEqual(response.status_code, 302)

    def test_utente_senza_ruolo_personale_non_gestisce(self):
        estraneo = User.objects.create_user("estraneo", password="password123!")
        estraneo.groups.add(Group.objects.get(name="Magazzino"))
        self.login(estraneo)
        response = self.client.get(reverse("hr:collaborator_list"))
        self.assertEqual(response.status_code, 403)


class MenuRuoliTest(CollaboratorTestBase):
    """Il menu deve riflettere i ruoli: l'amministratore non va mai limitato.

    Regressione: il context processor restituiva True per tutti i flag agli
    amministratori, compreso «is_collaborator_only», quindi l'admin vedeva il
    menu del collaboratore e sembrava aver perso i privilegi.
    """

    def test_i_flag_dell_amministratore_sono_corretti(self):
        from apps.core.context_processors import roles

        class Richiesta:
            user = self.admin

        flag = roles(Richiesta())["roles"]
        self.assertTrue(flag["is_admin"])
        self.assertTrue(flag["is_sales"])
        self.assertTrue(flag["is_hr"])
        self.assertFalse(
            flag["is_collaborator_only"],
            "l'amministratore non deve mai risultare limitato",
        )

    def test_l_amministratore_vede_il_menu_completo(self):
        self.login(self.admin)
        contenuto = self.client.get("/").content.decode("utf-8", "ignore")
        for voce in ("Contatti", "Articoli", "Preventivi", "Fatture emesse", "Collaboratori", "Impostazioni"):
            with self.subTest(voce=voce):
                self.assertIn(voce, contenuto, f"l'amministratore deve vedere «{voce}»")
        self.assertNotIn("Le mie ore", contenuto, "l'amministratore non deve vedere il menu del collaboratore")

    def test_l_amministratore_accede_a_tutte_le_sezioni(self):
        self.login(self.admin)
        for url in ("/", "/articoli/", "/contatti/", "/vendite/preventivi/", "/impostazioni/", "/personale/collaboratori/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_il_collaboratore_vede_solo_le_sue_voci(self):
        self.login(self.collab_user)
        contenuto = self.client.get(reverse("hr:collaborator_area")).content.decode("utf-8", "ignore")
        self.assertIn("Le mie ore", contenuto)
        self.assertNotIn("Fatture emesse", contenuto)
        self.assertNotIn("Preventivi", contenuto)

    def test_chi_ha_anche_un_altro_ruolo_vede_il_menu_completo(self):
        self.login(self.misto)
        contenuto = self.client.get("/").content.decode("utf-8", "ignore")
        self.assertIn("Preventivi", contenuto)
        self.assertNotIn("Le mie ore", contenuto)

    def test_utente_senza_ruoli_non_e_limitato_dal_menu(self):
        """Un utente senza gruppi non è un collaboratore: vede il menu normale."""
        from apps.core.context_processors import roles

        semplice = User.objects.create_user("semplice", password="password123!")

        class Richiesta:
            user = semplice

        self.assertFalse(roles(Richiesta())["roles"]["is_collaborator_only"])
