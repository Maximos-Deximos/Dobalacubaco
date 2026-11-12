# Telas de visualização e edição do perfil local.

from __future__ import annotations

from datetime import date
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, TextArea

from app.schemas.profile import ProfilePatch, UserProfile
from app.tui.services import TuiServices
from app.ui.cli import PROFILE_LABELS

PROFILE_FIXED_FIELDS = tuple(
    key for key, _label in PROFILE_LABELS if key not in {"links", "skills"}
)


# Tela de visualização do perfil padrão.
class ProfileScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back", "Voltar"),
        ("r", "reload", "Atualizar"),
    ]

    def __init__(self, services: TuiServices) -> None:
        super().__init__()
        self.services = services

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("Perfil", classes="title")
            yield Static("", id="profile-status", classes="hint")
            with VerticalScroll(classes="detail-box"):
                yield Static("", id="profile-content")
            with Horizontal(classes="actions"):
                yield Button("Criar perfil", id="init", variant="primary")
                yield Button("Editar", id="edit")
                yield Button("Atualizar", id="refresh")
                yield Button("Voltar", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        try:
            profile = self.services.users.get_default()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar perfil: {exc}", severity="error")
            return

        if profile is None:
            self.query_one("#profile-status", Static).update(
                "Nenhum perfil cadastrado."
            )
            self.query_one("#profile-content", Static).update(
                "Crie o perfil para reutilizar seus dados no agente."
            )
            self.query_one("#init", Button).disabled = False
            self.query_one("#edit", Button).disabled = True
            return

        self.query_one("#profile-status", Static).update(
            f"Perfil padrão: {profile.name} (id={profile.id})"
        )
        self.query_one("#profile-content", Static).update(_format_profile(profile))
        self.query_one("#init", Button).disabled = True
        self.query_one("#edit", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "init":
                self._ensure_default()
            case "edit":
                self._edit()
            case "refresh":
                self._load()
            case "back":
                self.action_back()

    def _ensure_default(self) -> None:
        try:
            profile, created = self.services.users.ensure_default()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao criar perfil: {exc}", severity="error")
            return

        self._load()
        message = (
            f"Perfil '{profile.name}' criado."
            if created
            else f"Perfil '{profile.name}' já existia."
        )
        self.notify(message, severity="information")

    def _edit(self) -> None:
        try:
            profile = self.services.users.get_default()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao carregar perfil: {exc}", severity="error")
            return

        if profile is None:
            self.notify("Crie o perfil antes de editar.", severity="warning")
            return

        self.app.push_screen(
            ProfileEditScreen(self.services, profile),
            self._after_edit,
        )

    async def _after_edit(self, result: object) -> None:
        if result:
            self._load()

    def action_reload(self) -> None:
        self._load()

    def action_back(self) -> None:
        self.app.pop_screen()


# Formulário de edição do perfil.
class ProfileEditScreen(Screen):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancelar"),
        Binding("ctrl+s", "save", "Salvar"),
    ]

    def __init__(self, services: TuiServices, profile: UserProfile) -> None:
        super().__init__()
        self.services = services
        self.profile = profile

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="screen-body"):
            yield Static("Editar perfil", classes="title")
            with VerticalScroll(classes="profile-form"):
                for key, label in PROFILE_LABELS:
                    if key in {"links", "skills"}:
                        continue
                    value = getattr(self.profile, key)
                    yield Label(label)
                    yield Input(
                        value="" if value is None else str(value),
                        id=f"profile-{key}",
                    )

                yield Label("Links (um por linha, formato chave=valor)")
                yield TextArea(
                    text=_format_pairs(self.profile.links),
                    id="profile-links",
                )
                yield Label("Habilidades (separadas por vírgula)")
                yield Input(
                    value=", ".join(self.profile.skills),
                    id="profile-skills",
                )
                yield Label(
                    "Respostas personalizadas (uma por linha, chave=valor)"
                )
                yield TextArea(
                    text=_format_pairs(self.profile.custom_answers),
                    id="profile-custom",
                )
            with Horizontal(classes="actions"):
                yield Button("Salvar", id="save", variant="primary")
                yield Button("Cancelar", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#profile-full_name", Input).focus()

    def _collect_patch(self) -> ProfilePatch:
        changes: dict[str, object] = {}
        for key in PROFILE_FIXED_FIELDS:
            raw = self.query_one(f"#profile-{key}", Input).value.strip()
            if key == "birth_date":
                changes[key] = date.fromisoformat(raw) if raw else None
            else:
                changes[key] = raw or None

        changes["skills"] = [
            item.strip()
            for item in self.query_one("#profile-skills", Input).value.split(",")
            if item.strip()
        ]
        changes["links"] = _parse_pairs(
            self.query_one("#profile-links", TextArea).text
        )
        changes["custom_answers"] = _parse_pairs(
            self.query_one("#profile-custom", TextArea).text
        )
        return ProfilePatch(**changes)

    def _save(self) -> None:
        try:
            patch = self._collect_patch()
            self.services.users.update(self.profile.id, patch)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Erro ao salvar perfil: {exc}", severity="error")
            return

        self.notify("Perfil atualizado.", severity="information")
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.action_cancel()

    def action_save(self) -> None:
        self._save()

    def action_cancel(self) -> None:
        self.dismiss(False)


# Formata o perfil para exibição.
def _format_profile(profile: UserProfile) -> str:
    lines: list[str] = []
    for key, label in PROFILE_LABELS:
        value = getattr(profile, key)
        if value in (None, "", [], {}):
            continue
        lines.append(f"{label}: {value}")

    if profile.links:
        lines.append("")
        lines.append("Links:")
        for key in sorted(profile.links):
            lines.append(f"  {key}: {profile.links[key]}")

    if profile.skills:
        lines.append("")
        lines.append("Habilidades:")
        lines.append("  " + ", ".join(profile.skills))

    if profile.custom_answers:
        lines.append("")
        lines.append("Respostas personalizadas:")
        for key in sorted(profile.custom_answers):
            lines.append(f"  {key}: {profile.custom_answers[key]}")

    return "\n".join(lines) if lines else "Nenhum dado preenchido."


# Converte um dicionário em linhas chave=valor.
def _format_pairs(values: dict[str, str]) -> str:
    return "\n".join(f"{key}={values[key]}" for key in sorted(values))


# Converte linhas chave=valor em um dicionário.
def _parse_pairs(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError(
                f"Linha {line_number}: use o formato chave=valor."
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Linha {line_number}: a chave não pode ser vazia.")
        values[key] = value.strip()
    return values
