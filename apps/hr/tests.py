"""Test di dipendenti, registrazione ore, ferie e registro presenze."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.core.models import TimeStampedModel  # noqa: F401  (verifica import di base)

from .models import Employee, LeaveRequest, TimeEntry, working_days

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
