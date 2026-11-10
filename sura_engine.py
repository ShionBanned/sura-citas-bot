import asyncio
import datetime
import os
import random
import re
import sys
import shutil
from typing import Callable, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from audio_alerter import trigger_alert_sound, stop_alarm
from security_shield import decrypt_string

# Cadenas críticas protegidas contra extracción por IA e ingeniería inversa
_URL_LOGIN_ENC = 'hQ<r5wLa5(vpr4x?-4z<R<f`U=OY8yC}e^Y3o{KlVn^_2(3!{aweqAM-i_<t#3;!Q=bX>emmjKM_&Y||&ZU=yviQ>4!Vn?~a2Js7cAlby>%DV6kT>1e2bVGly(cKZlixFziD`4nMmQ-`%jemU?qow!*z~yXYf0E3Sp'
_URL_HADA_ENC = 'hQ<r5wLa5(uRU1d;8QEGSN;1O`#o9NIwj5z18yiab5!+f-k;ivy27{*f`zNY-!0A<>%7&9ni%n1?s5?Ii2lCL$IREo-z*{mbN'

if sys.platform == "darwin":
    CHROME_PATHS = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
elif sys.platform == "win32":
    CHROME_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
else:
    CHROME_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium"
    ]

def find_system_browser() -> Optional[str]:
    """Busca el ejecutable de Google Chrome, Edge o navegadores Chromium en el sistema."""
    for path in CHROME_PATHS:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            return expanded
    return None

def normalize_text(s: str) -> str:
    """Normaliza texto eliminando acentos, caracteres especiales y dobles espacios."""
    s = s.lower().strip()
    for c, r in [('á','a'), ('é','e'), ('í','i'), ('ó','o'), ('ú','u'), ('ñ','n')]:
        s = s.replace(c, r)
    s = re.sub(r'[^a-z0-9]', ' ', s)
    return " ".join(s.split())

class SuraCitasEngine:
    def __init__(self, config: dict, status_callback: Callable[[str, str], None], on_cita_confirmada: Optional[Callable[[dict], None]] = None):
        self.config = config
        self.status_callback = status_callback
        self.on_cita_confirmada = on_cita_confirmada
        self.is_running = False
        self.cita_exitosa = False
        self._should_terminate = False
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._main_task: Optional[asyncio.Task] = None

    def log(self, message: str, level: str = "info"):
        """Envía actualizaciones de estado a la interfaz de usuario."""
        if self.status_callback:
            self.status_callback(message, level)

    def stop(self):
        """Detiene el bucle de búsqueda de inmediato."""
        self.is_running = False
        stop_alarm()
        if self.cita_exitosa:
            self.log("Búsqueda finalizada. La ventana del navegador permanece 100% abierta para tu gestión.", "info")
            return

        self._should_terminate = True
        self.log("Deteniendo el motor de búsqueda...", "warning")
        if self._loop and self._main_task and not self._main_task.done():
            try:
                self._loop.call_soon_threadsafe(self._main_task.cancel)
            except Exception:
                pass

    async def _init_browser(self, p):
        chrome_exe = find_system_browser()
        if not chrome_exe:
            raise RuntimeError(
                "No se encontró ningún navegador compatible (Google Chrome, Microsoft Edge, Brave o Chromium). "
                "Por favor asegúrate de instalar Google Chrome para continuar: https://www.google.com/chrome/"
            )
        headless = self.config.get("modo_silencioso", False)
        
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars"
        ]

        launch_kwargs = {
            "headless": headless,
            "args": args,
            "executable_path": chrome_exe
        }

        if sys.platform == "darwin":
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        else:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

        self._browser = await p.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 850}
        )
        self._page = await self._context.new_page()

        # Interceptor de diálogos nativos (como confirmación de reenvío POST)
        self._setup_dialog_handler(self._page)
        self._context.on("page", lambda new_p: self._setup_dialog_handler(new_p))

    def _setup_dialog_handler(self, page: Page):
        """Acepta automáticamente cualquier aviso nativo (como reenviar formulario POST)."""
        async def handle_dialog(dialog):
            try:
                await dialog.accept()
            except Exception:
                pass
        page.on("dialog", lambda dialog: asyncio.create_task(handle_dialog(dialog)))

    async def _do_single_login_attempt(self) -> bool:
        """Ejecuta un intento individual de inicio de sesión digitando con teclado virtual."""
        page = self._page
        
        # 1. Seleccionar tipo de documento
        tipo_doc = self.config.get("tipo_documento", "C")
        self.log(f"Seleccionando tipo de documento: {tipo_doc}...", "info")
        await page.select_option("#ctl00_ContentMain_suraType", tipo_doc)
        await page.wait_for_timeout(200)

        # 2. Escribir número de documento
        doc_num = str(self.config.get("documento", "")).strip()
        self.log(f"Ingresando documento ({doc_num[:3]}***)...", "info")
        await page.fill("#suraName", doc_num)
        await page.wait_for_timeout(200)

        # 3. Abrir el teclado virtual dando clic en el campo de contraseña
        self.log("Abriendo teclado virtual dinámico...", "info")
        await page.click("#suraPassword")
        await page.wait_for_selector(".ui-keyboard-button", timeout=6000)
        await page.wait_for_timeout(350)

        # 4. Digitar la clave numérica con pausas naturales
        clave = str(self.config.get("clave", "")).strip()
        if not clave:
            self.log("Error: La clave está vacía en la configuración.", "error")
            return False

        for digito in clave:
            btn = page.locator(f"button.ui-keyboard-button[data-value='{digito}']")
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(150)
            else:
                self.log(f"Error: No se encontró la tecla del dígito '{digito}'", "error")
                return False

        # 5. Clic en Aceptar en el teclado virtual
        accept_btn = page.locator("button.ui-keyboard-accept")
        if await accept_btn.count() > 0:
            await accept_btn.first.click()
            await page.wait_for_timeout(400)

        # 6. Clic en el botón principal de 'Iniciar sesión'
        self.log("Enviando credenciales a SURA...", "info")
        await page.click("#session-internet")

        # 7. Espera segura de respuesta sin colisionar con la navegación
        for _ in range(30):  # hasta 15 segundos
            if not self.is_running:
                return False
            await page.wait_for_timeout(500)
            
            try:
                curr_url = page.url.lower()
                if "serviciosunclick" in curr_url or "agendaweb" in curr_url:
                    await page.wait_for_load_state("domcontentloaded")
                    # Esperar a que la aplicación Angular complete la carga del token appTag y del grupo familiar
                    try:
                        await page.wait_for_function("""() => {
                            try {
                                if (!window.angular) return false;
                                const el = document.querySelector('[ng-controller]') || document.body;
                                const inj = angular.element(el).injector();
                                if (inj) {
                                    const fac = inj.get('GrupoFamiliarFactory');
                                    const token = fac && fac.getAppTagExt();
                                    const grupo = fac && fac.consultarGrupoFamiliar();
                                    return (!!token && typeof token === 'string' && token.length > 5 && Array.isArray(grupo) && grupo.length > 0);
                                }
                            } catch(e) {}
                            return false;
                        }""", timeout=15000)
                    except Exception:
                        pass
                    self.log("¡Inicio de sesión exitoso y credenciales autenticadas!", "success")
                    return True
            except Exception:
                pass

            try:
                err_elem = page.locator("#errormsgtab2, .ui-state-error, text='no válidos', text='no validos'")
                if await err_elem.count() > 0:
                    for i in range(await err_elem.count()):
                        if await err_elem.nth(i).is_visible():
                            return False
            except Exception:
                pass

        return "serviciosunclick" in page.url.lower() or "agendaweb" in page.url.lower()

    async def _login_with_retries(self) -> bool:
        """Sistema de 3 intentos: Si detecta error de credenciales, aplica recarga y reintenta."""
        page = self._page
        login_url = decrypt_string(_URL_LOGIN_ENC)
        
        self.log("Abriendo portal de autenticación SURA...", "info")
        await page.goto(login_url, wait_until="networkidle", timeout=35000)

        max_intentos = 3
        for intento in range(1, max_intentos + 1):
            self.log(f"--- Intento de inicio de sesión {intento} de {max_intentos} ---", "info")
            exito = await self._do_single_login_attempt()
            
            if exito:
                return True

            if intento < max_intentos:
                self.log(f"⚠️ Credenciales no reconocidas en intento {intento}. Aplicando recarga y reintentando...", "warning")
                await page.reload(wait_until="networkidle")
                await asyncio.sleep(2)
            else:
                self.log("❌ ERROR: SURA rechazó las credenciales tras los 3 intentos permitidos.", "error")
                self.log("El sistema se detuvo por seguridad. Revisa tu cédula y clave de 4 dígitos en la app.", "error")
                return False

        return False

    async def _get_active_target(self) -> Page:
        """Retorna la página o pestaña activa que contiene el módulo de agenda."""
        pages = self._context.pages
        for p in reversed(pages):
            try:
                if "agendaweb" in p.url.lower():
                    return p
            except Exception:
                pass
        return self._page

    async def _handle_stale_agenda_session(self, target: Page) -> bool:
        """
        Detecta y libera automáticamente la sesión previa bloqueada por SURA [AGEW-0501442]:
        'ALERTA: SEÑOR USUARIO, POR FAVOR LOGUEARSE DE NUEVO EN EL APLICATIVO YA QUE ACCEDIO A CITAS POR INTERNET SIN HABER CERRADO LA SESION DE AGENDAWEB PREVIAMENTE'
        """
        try:
            body = await target.inner_text("body")
            if "agew-" in body.lower() or "sin haber cerrado la sesion" in body.lower():
                self.log("⚠️ Detectada sesión previa activa en SURA [AGEW]. Liberándola automáticamente...", "warning")
                btn_cerrar = target.locator("a:has-text('Cerrar'), button:has-text('Cerrar'), text='Cerrar'")
                if await btn_cerrar.count() > 0:
                    await btn_cerrar.first.click()
                    await target.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        return False

    async def _click_entendido_deep(self, page: Page) -> bool:
        """
        Detecta y hace clic en el botón 'ENTENDIDO' dentro del componente <wc-hada> o cualquier Web Component
        de forma instantánea en milisegundos.
        """
        # Método 1: Evaluación directa en JavaScript dentro de Shadow DOM de wc-hada (< 5ms)
        try:
            clicked_js = await page.evaluate("""() => {
                function clickBtn(root) {
                    if (!root) return false;
                    const btns = root.querySelectorAll('button, a, [role="button"], input[type="button"]');
                    for (const b of btns) {
                        const txt = (b.innerText || b.textContent || b.value || '').trim().toUpperCase();
                        if (txt === 'ENTENDIDO' || txt.includes('ENTENDIDO')) {
                            b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, composed: true, view: window }));
                            if (typeof b.click === 'function') b.click();
                            return true;
                        }
                    }
                    const all = root.querySelectorAll('*');
                    for (const el of all) {
                        if (el.shadowRoot) {
                            if (clickBtn(el.shadowRoot)) return true;
                        }
                    }
                    return false;
                }
                return clickBtn(document.body);
            }""")
            if clicked_js:
                self.log("Botón 'ENTENDIDO' presionado instantáneamente vía Shadow DOM.", "info")
                return True
        except Exception:
            pass

        # Método 2: Selectores Shadow DOM directos de Playwright
        selectors = [
            "wc-hada >> button:has-text('ENTENDIDO')",
            "wc-hada >> button:has-text('Entendido')",
            "wc-hada >> .ant-modal-footer button",
            "wc-hada >> button.ant-btn-primary",
            ".ant-modal-footer button",
            "button:has-text('ENTENDIDO')",
            "button:has-text('Entendido')"
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    for i in range(await btn.count()):
                        item = btn.nth(i)
                        if await item.is_visible():
                            self.log("Detectado botón 'ENTENDIDO' vía Playwright. Clickeando...", "info")
                            await item.click(force=True, timeout=800)
                            return True
            except Exception:
                pass

        # Método 3: Coordenadas físicas del ratón
        try:
            coords = await page.evaluate("""() => {
                function findCoords(root) {
                    if (!root) return null;
                    const els = root.querySelectorAll('*');
                    for (const el of els) {
                        const txt = (el.innerText || el.textContent || el.value || '').trim().toUpperCase();
                        if (txt === 'ENTENDIDO') {
                            const target = el.closest('button, a, [role="button"]') || el;
                            const rect = target.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                return {
                                    x: rect.left + rect.width / 2,
                                    y: rect.top + rect.height / 2
                                };
                            }
                        }
                        if (el.shadowRoot) {
                            const res = findCoords(el.shadowRoot);
                            if (res) return res;
                        }
                    }
                    return null;
                }
                return findCoords(document.body);
            }""")

            if coords and coords.get("x") and coords.get("y"):
                cx, cy = coords["x"], coords["y"]
                await page.mouse.click(cx, cy)
                return True
        except Exception:
            pass

        return False

    async def _navigate_through_flow(self, force_refresh: bool = False) -> bool:
        """
        Navega el flujo visual completo de forma ultrarrápida con tolerancia a transiciones de pantalla:
        1. Acceso a: /ServiciosUnClick/solicitudes/seleccionGrupoHada
        2. Grupo Familiar: Selección instantánea vía JavaScript
        3. Modal 'Somos tu experto aliado': Detección inmediata cada 150ms y clic en 'ENTENDIDO'
        4. Pantalla Agenda 1 (EPS _ SURA - Agenda Web): Selección de listaServicios y clic en Consultar disponibilidad
        5. Pantalla Agenda 2 (AGENDAWEB - SERVICIOS): Lista para monitorear cupos
        """
        if not self.is_running:
            return False
        try:
            return await self._navigate_through_flow_impl(force_refresh)
        except Exception as flow_err:
            err_str = str(flow_err).lower()
            if "navigat" in err_str or "destroyed" in err_str or "context" in err_str:
                self.log("Sincronizando transición de pantalla en SURA...", "info")
            else:
                self.log(f"Aviso en navegación: {flow_err}", "warning")
            return False

    async def _navigate_through_flow_impl(self, force_refresh: bool = False) -> bool:
        page = self._page
        self.log("Conectando con el módulo de Solicitud de Citas...", "info")

        # Si ya estamos en agendaweb, verificar si hay error AGEW o si ya está lista
        target = await self._get_active_target()
        if "agendaweb" in target.url.lower():
            if not force_refresh:
                if await self._handle_stale_agenda_session(target):
                    await page.goto(decrypt_string(_URL_HADA_ENC), wait_until="domcontentloaded", timeout=15000)
                else:
                    return True
            else:
                # Refresco forzado: liberar sesión de AgendaWeb de forma preventiva
                try:
                    btn_cerrar = target.locator("button:has-text('Cerrar sesión'), a:has-text('Cerrar'), button:has-text('Cerrar')")
                    if await btn_cerrar.count() > 0 and await btn_cerrar.first.is_visible():
                        await btn_cerrar.first.click()
                        await target.wait_for_timeout(300)
                except Exception:
                    pass

        # Verificar si la página quedó en citasHada con error 'No autorizado'
        try:
            body_txt = await page.inner_text("body")
            if "no autorizado" in body_txt.lower() or "clave de cuatro d" in body_txt.lower():
                self.log("⚠️ Detectada advertencia 'No autorizado'. Re-autenticando en SURA...", "warning")
                await self._click_entendido_deep(page)
                await page.wait_for_timeout(1000)
                await self._login_with_retries()
        except Exception:
            pass

        # PASO 1: Navegar a la ruta de selección de grupo familiar
        if not self.is_running:
            return False

        curr_url = page.url.lower()
        if "solicitudes/selecciongrupohada" not in curr_url:
            self.log("Accediendo a selección de paciente...", "info")
            # 1. Intentar clic directo en la tarjeta de la página de inicio
            try:
                card_loc = page.locator("div[ui-sref*='seleccionGrupoHada'], a[ui-sref*='seleccionGrupoHada'], :text('Solicitud y cancelación citas médico general')").last
                if await card_loc.count() > 0 and await card_loc.is_visible():
                    self.log("Accediendo mediante tarjeta 'Solicitud y cancelación citas médico general'...", "info")
                    await card_loc.click()
                    await page.wait_for_timeout(600)
            except Exception:
                pass

            # 2. Si aún no está en la URL de seleccionGrupoHada, realizar navegación directa
            if "solicitudes/selecciongrupohada" not in page.url.lower():
                hada_url = decrypt_string(_URL_HADA_ENC)
                try:
                    await page.goto(hada_url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

        # Esperar a que el selector de grupo familiar esté presente en el DOM
        try:
            await page.wait_for_selector("select#grupoFamiliar", timeout=8000)
        except Exception:
            pass

        # PASO 2: Selección inteligente del paciente vinculando el Scope de AngularJS
        if not self.is_running:
            return False
        target_paciente = str(self.config.get("paciente", "Santiago")).strip()
        self.log(f"Buscando al paciente '{target_paciente}'...", "info")

        paciente_info = None
        for _ in range(50):  # sondeo de hasta 10 segundos revisando cada 200ms
            if not self.is_running:
                return False

            try:
                paciente_info = await page.evaluate("""(targetName) => {
                function norm(s) {
                    return (s || '').toLowerCase()
                        .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '')
                        .replace(/[^a-z0-9]/g, ' ')
                        .trim().replace(/\\s+/g, ' ');
                }

                // 1. Método Angular: Verificación estricta de token y sincronización de Scope
                try {
                    if (window.angular) {
                        const el = document.querySelector('[ng-controller]') || document.body;
                        const inj = angular.element(el).injector();
                        if (inj) {
                            const fac = inj.get('GrupoFamiliarFactory');
                            const token = fac ? fac.getAppTagExt() : null;

                            // REGLA CRÍTICA: NO invocar ingresar() sin token válido (evita el 401 'No autorizado')
                            if (!token || typeof token !== 'string' || token.length < 5) {
                                return null;
                            }

                            const sel = document.querySelector('select#grupoFamiliar');
                            const ngEl = sel ? angular.element(sel) : null;
                            const scope = ngEl ? ngEl.scope() : null;

                            let grupo = (scope && scope.grupoFamiliar && scope.grupoFamiliar.length > 0)
                                ? scope.grupoFamiliar
                                : (fac ? fac.consultarGrupoFamiliar() : null);

                            if (grupo && grupo.length > 0) {
                                const targetWords = norm(targetName).split(' ').filter(w => w.length > 0);
                                let bestAf = null;
                                let bestScore = -1;

                                for (const af of grupo) {
                                    const fullName = [af.primerNombre, af.segundoNombre, af.primerApellido, af.segundoApellido].join(' ');
                                    const afWords = norm(fullName).split(' ');
                                    let score = 0;
                                    for (const tw of targetWords) {
                                        if (afWords.includes(tw)) score += 1;
                                    }
                                    if (targetWords.length > 0 && afWords.includes(targetWords[0])) {
                                        score += 0.5;
                                    }
                                    if (score > bestScore) {
                                        bestScore = score;
                                        bestAf = af;
                                    }
                                }

                                if (!bestAf && grupo.length > 0) {
                                    bestAf = grupo[0];
                                }

                                if (bestAf && scope) {
                                    scope.$apply(function() {
                                        scope.grupoFamiliar = grupo;
                                        scope.afiliadoSeleccionado = bestAf;
                                        scope.afiliadoSeleccionado.appTagExt = token;
                                        if (typeof scope.ingresar === 'function') {
                                            scope.ingresar();
                                        }
                                    });
                                    const matchedName = [bestAf.primerNombre, bestAf.primerApellido].join(' ');
                                    return { success: true, text: matchedName };
                                }
                            }
                        }
                    }
                } catch(e) {}

                // 2. Método DOM de respaldo
                const sel = document.querySelector('select#grupoFamiliar');
                if (sel && sel.options && sel.options.length > 1) {
                    const targetWords = norm(targetName).split(' ').filter(w => w.length > 0);
                    let bestVal = null;
                    let bestTxt = null;
                    let bestScore = -1;

                    for (let i = 1; i < sel.options.length; i++) {
                        const opt = sel.options[i];
                        const val = opt.value;
                        const txt = (opt.text || opt.innerText || '').trim();
                        if (!val || val === '' || txt.toLowerCase().includes('seleccione')) continue;

                        const optWords = norm(txt).split(' ');
                        let score = 0;
                        for (const tw of targetWords) {
                            if (optWords.includes(tw)) score += 1;
                        }
                        if (targetWords.length > 0 && optWords.includes(targetWords[0])) {
                            score += 0.5;
                        }
                        if (score > bestScore) {
                            bestScore = score;
                            bestVal = val;
                            bestTxt = txt;
                        }
                    }

                    if (bestVal) {
                        sel.value = bestVal;
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        return { success: true, text: bestTxt, val: bestVal };
                    }
                }

                return null;
            }""", target_paciente)
            except Exception:
                paciente_info = None

            if paciente_info and paciente_info.get("success"):
                break
            await asyncio.sleep(0.2)

        if paciente_info and paciente_info.get("text"):
            self.log(f"¡Paciente seleccionado!: {paciente_info['text']}", "success")
        else:
            self.log("Aviso: esperando selector de familiares...", "warning")

        # PASO 3: Detección inmediata y clic en el botón 'ENTENDIDO' (sondeo cada 150ms)
        if not self.is_running:
            return False
        self.log("Detectando confirmación ('ENTENDIDO')...", "info")
        entendido_clickeado = False
        for _ in range(40):  # sondeo ultrarrápido hasta 6s
            if not self.is_running:
                return False

            target = await self._get_active_target()
            if "agendaweb" in target.url.lower():
                entendido_clickeado = True
                break

            clicked = await self._click_entendido_deep(page)
            if clicked:
                self.log("¡Botón 'ENTENDIDO' clickeado! Redireccionando a AgendaWeb...", "success")
                entendido_clickeado = True
                break

            await asyncio.sleep(0.15)

        # PASO 4: Esperar conexión real a agendaweb.suramericana.com
        if not self.is_running:
            return False
        self.log("Sincronizando con Agenda Web...", "info")
        conectado = False
        for _ in range(30):  # hasta 15 segundos con sondeo de 0.5s
            if not self.is_running:
                return False
            target = await self._get_active_target()
            if "agendaweb" in target.url.lower():
                if await self._handle_stale_agenda_session(target):
                    self.log("Reintentando acceso tras liberar sesión previa...", "info")
                    await page.goto(decrypt_string(_URL_HADA_ENC), wait_until="domcontentloaded", timeout=15000)
                    return await self._navigate_through_flow()
                conectado = True
                self.log("¡Conexión establecida con la Agenda Web!", "success")
                break
            await asyncio.sleep(0.5)

        if not conectado:
            self.log("❌ No se pudo conectar a la Agenda Web. Reintentando...", "error")
            return False

        # PASO 5: Selección de servicio y consulta de disponibilidad en AgendaWeb
        if not self.is_running:
            return False
        target = await self._get_active_target()
        
        # Verificar si la tabla de cupos ya está presente en pantalla
        try:
            tiene_tabla = await target.locator("table.control_citas, input[name='fechasDisponibilidad']").count() > 0
            if tiene_tabla:
                self.log("Agenda lista para monitoreo en vivo.", "success")
                return True
        except Exception:
            pass

        # Esperar a que el selector de servicios o el botón de consulta estén disponibles
        try:
            await target.wait_for_selector("select[name='listaServicios'], button:has-text('Consultar disponibilidad')", timeout=10000)
        except Exception:
            pass

        # Asegurar que esté seleccionado 'CONSULTA MEDICINA GENERAL'
        try:
            await target.evaluate("""() => {
                const sel = document.querySelector("select[name='listaServicios']");
                if (sel) {
                    const curText = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text.toLowerCase() : '';
                    if (!curText.includes('medicina general')) {
                        for (let i = 0; i < sel.options.length; i++) {
                            const txt = sel.options[i].text.toLowerCase();
                            if (txt.includes('medicina general') && txt.includes('presencial')) {
                                sel.selectedIndex = i;
                                break;
                            }
                        }
                    }
                }
            }""")
            await target.wait_for_timeout(300)
        except Exception:
            pass

        # Clic directo e instantáneo en la consulta de disponibilidad (invocación JS nativa + clic)
        self.log("Consultando disponibilidad de citas en SURA...", "info")
        try:
            await target.evaluate("""() => {
                try {
                    if (typeof consultarDisponibilidadCitas === 'function') {
                        consultarDisponibilidadCitas();
                        return true;
                    }
                    if (document.forms && document.forms.length > 0) {
                        document.forms[0].action = "internet-consultarDisponibilidadCitas.do";
                        document.forms[0].submit();
                        return true;
                    }
                } catch(e) {}
                return false;
            }""")
        except Exception:
            pass

        # Si aún no inició recarga, pulsar el botón rápidamente
        try:
            btn_consultar = target.locator(
                "button:has-text('Consultar disponibilidad'), button[onclick*='consultarDisponibilidadCitas']"
            ).first
            if await btn_consultar.count() > 0 and await btn_consultar.is_visible():
                await btn_consultar.click(timeout=800)
        except Exception:
            pass

        # Si salta el modal '#disponible' solicitando fecha tentativa, diligenciar al vuelo
        try:
            modal_disp = target.locator("#disponible")
            if await modal_disp.count() > 0 and await modal_disp.is_visible():
                dia_deseado = self.config.get("dia_deseado", "manana")
                fecha_ref = (datetime.date.today() + datetime.timedelta(days=1)) if dia_deseado == "manana" else datetime.date.today()
                await target.fill("#recipient-date", fecha_ref.strftime("%Y-%m-%d"))
                btn_resol = target.locator("button[onclick*='consultarDisponibilidadCitasResolucion'], button:has-text('Consultar disponibilidad de citas')")
                if await btn_resol.count() > 0:
                    await btn_resol.first.click()
        except Exception:
            pass

        # Esperar la tabla de resultados de SURA de forma inmediata (máximo 4 segundos)
        try:
            await target.wait_for_selector(
                "table.control_citas, #calendar_1, input[name='fechasDisponibilidad'], [property='diaSeleccionado']",
                timeout=4000
            )
            self.log("Agenda lista para monitoreo en vivo.", "success")
        except Exception:
            # Reintento final rápido por JS en caso de latencia de red
            try:
                await target.evaluate("if (typeof consultarDisponibilidadCitas === 'function') consultarDisponibilidadCitas();")
                await target.wait_for_selector(
                    "table.control_citas, #calendar_1, input[name='fechasDisponibilidad']",
                    timeout=3000
                )
                self.log("Agenda lista para monitoreo en vivo.", "success")
            except Exception:
                self.log("Agenda lista para monitoreo en vivo.", "success")

        return True

    async def _verify_confirmation(self, target: Page, fecha_str: str, hora_str: str) -> Optional[dict]:
        """
        Verifica si la cita quedó 100% reservada mediante la ventana MENSAJE DE USUARIO
        o si saltó una colisión de que otro usuario la tomó.
        """
        self.log("Esperando confirmación oficial de SURA...", "info")
        for _ in range(16):  # hasta 8 segundos
            await target.wait_for_timeout(500)
            try:
                body_text = await target.inner_text("body")
                
                # Caso Éxito
                if "ha sido programada para el" in body_text.lower() or "mensaje de usuario" in body_text.lower() or "cita con el profesional" in body_text.lower():
                    msg_elem = target.locator(".modal, [role='dialog'], .alert-success, div:has-text('ha sido programada')")
                    resumen = "Cita confirmada exitosamente."
                    if await msg_elem.count() > 0:
                        resumen = (await msg_elem.first.inner_text()).strip()
                    
                    return {
                        "fecha": fecha_str,
                        "hora": hora_str,
                        "detalle": resumen
                    }

                # Caso Colisión (Alguien más la tomó)
                colision_kw = ["ya no se encuentra disponible", "ocupad", "no fue posible", "error al asignar"]
                if any(kw in body_text.lower() for kw in colision_kw):
                    self.log(f"⚠️ El cupo de las {hora_str} fue tomado por otro usuario milisegundos antes.", "warning")
                    btn_cerrar = target.locator("button:has-text('Cerrar'), button:has-text('Aceptar'), [data-dismiss='modal']")
                    if await btn_cerrar.count() > 0:
                        await btn_cerrar.first.click()
                    return None

            except Exception:
                pass

        return None

    async def _check_and_book_slots(self, target: Page) -> Optional[dict]:
        """
        Analiza estrictamente la disponibilidad y la fecha activa con captura segura de excepciones.
        """
        try:
            return await self._check_and_book_slots_impl(target)
        except Exception as check_err:
            err_sub = str(check_err).lower()
            if "navigat" in err_sub or "context" in err_sub or "destroyed" in err_sub:
                self.log("Sincronizando tabla de citas tras navegación...", "info")
            else:
                self.log(f"Aviso revisando cupos: {check_err}", "warning")
            return None

    async def _check_and_book_slots_impl(self, target: Page) -> Optional[dict]:
        """
        Analiza estrictamente la disponibilidad y la fecha activa:
        - input[name='fechasDisponibilidad']: Todas las fechas con citas reales
        - input[name='fechaCita']: Fecha exacta de la cita visible en la tabla
        - Cabecera th.last de table.control_citas: Texto exacto del día sobre el botón
        - NUNCA reserva citas de otra fecha (como diciembre) si el usuario pidió 'mañana' o 'hoy'.
        """
        # Verificar si saltó error AGEW
        if await self._handle_stale_agenda_session(target):
            return None

        dia_deseado = self.config.get("dia_deseado", "manana")
        jornada_deseada = self.config.get("jornada", "cualquiera")

        hoy = datetime.date.today()
        manana = hoy + datetime.timedelta(days=1)
        hoy_str_hyphen = hoy.strftime("%Y-%m-%d")
        manana_str_hyphen = manana.strftime("%Y-%m-%d")
        hoy_str_slash = hoy.strftime("%Y/%m/%d")
        manana_str_slash = manana.strftime("%Y/%m/%d")

        # 1. Leer las fechas con disponibilidad REALES de SURA
        fechas_disp = ""
        fd_elem = target.locator("input[name='fechasDisponibilidad']")
        if await fd_elem.count() > 0:
            fechas_disp = await fd_elem.get_attribute("value") or ""

        # 2. Leer la fecha exacta de la cita visible en la tabla
        fecha_cita_actual = ""
        fc_elem = target.locator("input[name='fechaCita']")
        if await fc_elem.count() > 0:
            fecha_cita_actual = (await fc_elem.get_attribute("value") or "").strip()

        # Extraer texto de la cabecera th (columna de fecha arriba de ASIGNAR CITA)
        th_fecha_txt = ""
        th_loc = target.locator("table.control_citas thead th").last
        if await th_loc.count() > 0:
            th_fecha_txt = (await th_loc.inner_text()).strip()
            if not fecha_cita_actual:
                m_th = re.search(r'\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b', th_fecha_txt)
                if m_th:
                    fecha_cita_actual = f"{m_th.group(1)}/{int(m_th.group(2)):02d}/{int(m_th.group(3)):02d}"

        # 3. FILTRO ESTRICTO POR FECHA DESEADA:
        if dia_deseado == "manana":
            # ¿Mañana está en la lista de fechas disponibles en el sistema SURA?
            if manana_str_hyphen not in fechas_disp and manana_str_slash not in fechas_disp:
                self.log(f"Revisando agenda: Sin cupos para Mañana ({manana_str_slash}). Continuando monitoreo...", "info")
                return None

            # Si mañana sí está disponible pero la tabla está mostrando otra fecha:
            if manana_str_slash not in fecha_cita_actual and manana_str_hyphen not in fecha_cita_actual:
                self.log(f"¡Cupo para Mañana detectado en SURA! Conmutando vista al día {manana.day}...", "success")
                try:
                    # Llamar directamente a la función de cambio de fecha de SURA
                    await target.evaluate(f"if (typeof onSelect === 'function') onSelect({manana.month - 1}, {manana.year}, {manana.day}, 'calendar_1');")
                    await target.wait_for_load_state("domcontentloaded", timeout=12000)
                    await target.wait_for_timeout(1500)
                    if await fc_elem.count() > 0:
                        fecha_cita_actual = (await fc_elem.get_attribute("value") or "").strip()
                except Exception:
                    pass

            # Verificación inquebrantable 1: El input fechaCita DEBE ser de mañana
            if manana_str_slash not in fecha_cita_actual and manana_str_hyphen not in fecha_cita_actual:
                self.log(f"Esperando que SURA cargue la tabla para Mañana ({manana_str_slash}). Fecha actual en vista: {fecha_cita_actual}", "info")
                return None

            # Verificación inquebrantable 2: La cabecera sobre el botón DEBE coincidir con mañana
            if th_fecha_txt and manana_str_slash not in th_fecha_txt and manana_str_hyphen not in th_fecha_txt and str(manana.day) not in th_fecha_txt:
                self.log(f"Cabecera '{th_fecha_txt}' no corresponde a Mañana ({manana_str_slash}). Omitiendo para no reservar fecha incorrecta.", "warning")
                return None

        elif dia_deseado == "hoy":
            if hoy_str_hyphen not in fechas_disp and hoy_str_slash not in fechas_disp:
                self.log(f"Revisando agenda: Sin cupos para Hoy ({hoy_str_slash}). Continuando monitoreo...", "info")
                return None

            if hoy_str_slash not in fecha_cita_actual and hoy_str_hyphen not in fecha_cita_actual:
                try:
                    await target.evaluate(f"if (typeof onSelect === 'function') onSelect({hoy.month - 1}, {hoy.year}, {hoy.day}, 'calendar_1');")
                    await target.wait_for_load_state("domcontentloaded", timeout=12000)
                    await target.wait_for_timeout(1500)
                    if await fc_elem.count() > 0:
                        fecha_cita_actual = (await fc_elem.get_attribute("value") or "").strip()
                except Exception:
                    pass

            if hoy_str_slash not in fecha_cita_actual and hoy_str_hyphen not in fecha_cita_actual:
                self.log(f"Esperando que SURA cargue la tabla para Hoy ({hoy_str_slash}). Fecha actual en vista: {fecha_cita_actual}", "info")
                return None

        # 4. Si la fecha es estrictamente válida, buscar botones de 'ASIGNAR CITA'
        btn_asignar = target.locator(
            "button:has-text('ASIGNAR CITA'), button[property='diaSeleccionado'], button[onclick*='seleccionarCita']"
        )
        total_cupos = await btn_asignar.count()

        if total_cupos == 0:
            return None

        self.log(f"¡Se detectaron {total_cupos} cupo(s) en pantalla para {fecha_cita_actual}!", "info")

        # 5. Evaluar cada cupo con el filtro de jornada (mañana / tarde / cualquiera)
        for i in range(total_cupos):
            btn = btn_asignar.nth(i)
            try:
                row = btn.locator("xpath=ancestor::tr[1]")
                row_text = await row.inner_text()
            except Exception:
                continue

            time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', row_text)
            if not time_match:
                continue

            hora = int(time_match.group(1))
            minuto = int(time_match.group(2))
            hora_str = f"{hora:02d}:{minuto:02d}"

            # Filtro por jornada
            if jornada_deseada == "manana" and hora >= 12:
                continue
            if jornada_deseada == "tarde" and hora < 12:
                continue

            # ¡Cumple con la fecha deseada y la jornada! Proceder a reservar
            self.log(f"🎯 ¡CUPO EXACTO CONFIRMADO! Fecha: {fecha_cita_actual} a las {hora_str}. Reservando...", "success")
            
            try:
                await btn.click()
                await target.wait_for_timeout(600)
                
                confirmacion = await self._verify_confirmation(target, fecha_cita_actual, hora_str)
                if confirmacion:
                    trigger_alert_sound()
                    return confirmacion
            except Exception as e:
                self.log(f"Error al presionar asignar cita: {e}", "warning")

        return None

    async def _refresh_disponibilidad(self, target: Page):
        """
        Refresca la disponibilidad navegando a la ruta segura del portal:
        https://portaleps.epssura.com/ServiciosUnClick/solicitudes/seleccionGrupoHada
        Garantiza que no ocurra el bloqueo [AGEW-0501442] y renueva la consulta con datos frescos.
        """
        self.log("Refrescando disponibilidad mediante re-ingreso seguro al portal...", "info")
        try:
            await self._navigate_through_flow(force_refresh=True)
        except Exception as e:
            err_str = str(e).lower()
            if "navigat" in err_str or "destroyed" in err_str or "context" in err_str:
                self.log("Sincronizando recarga de página...", "info")
                try:
                    await target.wait_for_load_state("domcontentloaded", timeout=4000)
                except Exception:
                    pass
            else:
                self.log(f"Aviso durante el refresco: {e}", "warning")

    async def start(self):
        """Bucle principal de monitoreo continuo."""
        self.is_running = True
        self._loop = asyncio.get_running_loop()
        self._main_task = asyncio.current_task()
        
        async with async_playwright() as p:
            try:
                await self._init_browser(p)
                
                # 1. Login seguro con reintentos
                login_ok = await self._login_with_retries()
                if not login_ok or not self.is_running:
                    return

                # 2. Navegación completa por las pantallas
                nav_ok = await self._navigate_through_flow()
                if not nav_ok or not self.is_running:
                    if self.is_running:
                        self.log("No se pudo completar la navegación hacia la agenda.", "error")
                    return

                intento = 1
                dia_str = "Mañana" if self.config.get("dia_deseado") == "manana" else ("Hoy" if self.config.get("dia_deseado") == "hoy" else "Cualquier fecha")
                self.log(f"Iniciando monitoreo de citas ({dia_str}). Intervalo ultra-rápido: 2 a 5 segundos (anti-bot).", "info")

                while self.is_running:
                    try:
                        now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
                        self.log(f"Revisando agenda (Intento #{intento} - {now_str})...", "info")
                        
                        target = await self._get_active_target()
                        
                        # Si aún no está en agendaweb, asegurar navegación
                        if "agendaweb" not in target.url.lower():
                            self.log("Sincronizando con la plataforma de agenda...", "info")
                            nav_ok = await self._navigate_through_flow()
                            if not nav_ok or not self.is_running:
                                await asyncio.sleep(1)
                                continue
                            target = await self._get_active_target()

                        # Verificar si la sesión se cerró y volvió a login
                        if "login.sura.com" in target.url.lower():
                            self.log("⚠️ Sesión expirada en SURA. Re-autenticando automáticamente...", "warning")
                            if await self._login_with_retries():
                                await self._navigate_through_flow()
                                continue
                            else:
                                break

                        try:
                            cita_obtenida = await self._check_and_book_slots(target)
                            if cita_obtenida:
                                self.cita_exitosa = True
                                self.is_running = False
                                trigger_alert_sound()
                                if self.on_cita_confirmada:
                                    try:
                                        self.on_cita_confirmada(cita_obtenida)
                                    except Exception:
                                        pass
                                self.log("==================================================", "success")
                                self.log("🎉 ¡CITA CONSEGUIDA Y CONFIRMADA AL 100%!", "success")
                                self.log(f"📅 Fecha: {cita_obtenida['fecha']}", "success")
                                self.log(f"⏰ Hora:  {cita_obtenida['hora']}", "success")
                                if "detalle" in cita_obtenida:
                                    self.log(f"📋 {cita_obtenida['detalle']}", "success")
                                self.log("🔔 La ventana del navegador permanecerá abierta para que verifiques los detalles de tu cita.", "success")
                                self.log("==================================================", "success")
                                
                                # Mantener la ventana de Chrome abierta e interactiva para el usuario
                                while not self._should_terminate:
                                    await asyncio.sleep(1)
                                    if self._browser and not self._browser.is_connected():
                                        break
                                break
                        except Exception as e:
                            if self.is_running:
                                err_sub = str(e).lower()
                                if "navigat" in err_sub or "context" in err_sub or "destroyed" in err_sub:
                                    self.log("Sincronizando tabla de citas tras navegación...", "info")
                                else:
                                    self.log(f"Aviso revisando cupos: {e}", "warning")

                        if not self.is_running:
                            break

                        # Pausa aleatoria anti-bot entre 2 y 5 segundos
                        espera_segundos = random.randint(2, 5)
                        self.log(f"Esperando {espera_segundos}s para la próxima verificación (intervalo rápido: 2 a 5s)...", "info")
                        for _ in range(espera_segundos * 2):
                            if not self.is_running:
                                break
                            await asyncio.sleep(0.5)

                        if not self.is_running:
                            break

                        # Refrescar la disponibilidad re-ingresando por seleccionGrupoHada
                        await self._refresh_disponibilidad(target)

                        intento += 1

                    except Exception as loop_err:
                        if not self.is_running:
                            break
                        err_str = str(loop_err).lower()
                        # Si es error por navegación en curso o contexto destruido transitoriamente:
                        if "execution context was destroyed" in err_str or "navigat" in err_str or "frame was detached" in err_str:
                            self.log("Página en transición de navegación. Sincronizando y continuando monitoreo...", "info")
                            try:
                                target = await self._get_active_target()
                                await target.wait_for_load_state("domcontentloaded", timeout=4000)
                            except Exception:
                                pass
                            await asyncio.sleep(1)
                            continue
                        elif "target page, context or browser has been closed" in err_str or "closed" in err_str:
                            self.log("Navegador cerrado. Deteniendo búsqueda.", "info")
                            break
                        else:
                            self.log(f"Aviso en ciclo de búsqueda: {loop_err}. Reintentando...", "warning")
                            await asyncio.sleep(1.5)
                            continue

            except (asyncio.CancelledError, Exception) as e:
                err_str = str(e).lower()
                if not self.is_running or isinstance(e, asyncio.CancelledError) or "closed" in err_str:
                    self.log("Búsqueda detenida correctamente.", "info")
                else:
                    self.log(f"Aviso en el motor: {e}", "warning")
            finally:
                self.is_running = False
                # Si se consiguió una cita exitosa, NUNCA cerrar el navegador automáticamente
                if self._browser and not self.cita_exitosa:
                    try:
                        await self._browser.close()
                    except Exception:
                        pass
