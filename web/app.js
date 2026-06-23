const { createApp } = Vue

/* Material-style ripple: a circle that expands from the pointer. */
const ripple = {
  mounted(el) {
    el.addEventListener("pointerdown", (e) => {
      const rect = el.getBoundingClientRect()
      const size = Math.max(rect.width, rect.height) * 1.1
      const span = document.createElement("span")
      span.className = "ripple"
      span.style.width = span.style.height = size + "px"
      span.style.left = e.clientX - rect.left - size / 2 + "px"
      span.style.top = e.clientY - rect.top - size / 2 + "px"
      el.appendChild(span)
      span.addEventListener("animationend", () => span.remove())
    })
  },
}

const EpisodeCard = {
  props: ["episode", "languages", "busy", "canPublish", "saved"],
  emits: ["share", "regenerate", "delete", "save"],
  data() {
    return { regenLang: "" }
  },
  computed: {
    shareUrl() {
      return this.episode.share_key ? location.origin + "/s/" + this.episode.share_key : ""
    },
    downloadName() {
      return `${this.episode.theme_key}-${this.episode.date}-${this.episode.language}.mp3`
    },
    otherLanguages() {
      return this.languages.filter((l) => l.code !== this.episode.language)
    },
  },
  methods: {
    emitRegen() {
      if (!this.regenLang) return
      this.$emit("regenerate", { episode: this.episode, language: this.regenLang })
      this.regenLang = ""
    },
    async copyShare() {
      try {
        await navigator.clipboard.writeText(this.shareUrl)
        this.$root.flash("Lien copié")
      } catch (_) {
        this.$root.flash(this.shareUrl)
      }
    },
  },
  template: `
    <div class="episode">
      <div class="meta">
        <span class="chip">{{ episode.date }}</span>
        <span class="chip">{{ episode.language_label || episode.language }}</span>
        <span class="chip" v-if="episode.minutes">{{ episode.minutes }} min</span>
        <span class="chip" v-if="episode.sources && episode.sources.length">{{ episode.sources.length }} sources</span>
        <span class="chip" v-if="episode.tts_provider"><svg class="ic sm"><use href="#i-sound"></use></svg>{{ episode.tts_provider }}</span>
        <span class="chip accent" v-if="saved"><svg class="ic sm"><use href="#i-check"></use></svg>hors-ligne</span>
      </div>
      <div class="ep-summary" v-if="episode.summary">{{ episode.summary }}</div>
      <audio controls preload="none" :src="episode.audio_url"></audio>
      <div class="actions">
        <button class="btn tonal ripple-host" v-ripple :disabled="saved" @click="$emit('save', episode)">
          <svg class="ic"><use :href="saved ? '#i-check' : '#i-offline'"></use></svg>
          {{ saved ? 'Enregistré' : 'Enregistrer hors-ligne' }}
        </button>
        <a class="btn ripple-host" v-ripple :href="episode.audio_url" :download="downloadName"><svg class="ic"><use href="#i-download"></use></svg> Télécharger</a>
        <button class="btn ripple-host" v-ripple @click="$emit('share', episode)"><svg class="ic"><use href="#i-share"></use></svg> Partager</button>
        <template v-if="canPublish">
          <select class="btn" v-model="regenLang">
            <option value="">Autre langue…</option>
            <option v-for="l in otherLanguages" :key="l.code" :value="l.code">{{ l.label }}</option>
          </select>
          <button class="btn ripple-host" v-ripple :disabled="!regenLang || busy" @click="emitRegen">
            <span v-if="busy" class="spinner"></span> Régénérer
          </button>
          <button class="btn text danger ripple-host" v-ripple @click="$emit('delete', episode)"><svg class="ic"><use href="#i-trash"></use></svg></button>
        </template>
      </div>
      <div class="slider-row" v-if="shareUrl">
        <input readonly :value="shareUrl" @focus="$event.target.select()" />
        <button class="btn tonal ripple-host" v-ripple @click="copyShare">Copier</button>
      </div>
    </div>
  `,
}

createApp({
  components: { EpisodeCard },
  directives: { ripple },
  data() {
    return {
      user: null,
      needsSetup: false,
      authMode: "login",
      auth: { email: "", password: "", name: "" },
      authError: "",
      authBusy: false,
      menuOpen: false,
      online: navigator.onLine,
      view: "today",
      themes: [],
      languages: [],
      keys: [],
      users: [],
      schedules: [],
      cron: { installed: false, line: "", command: "" },
      smtpConfigured: false,
      duration: { min: 3, max: 20, default: 10 },
      jobs: {},
      keyInputs: {},
      saved: [],
      form: { icon: "🎙️", title: "", summary: "", research_brief: "", language: "fr", minutes: 10, mode: "once", hour: 7, weekday: 0 },
      weekdays: ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
      history: { theme: null, episodes: [] },
      toast: "",
      loaded: false,
    }
  },
  computed: {
    canPublish() {
      return !!this.user && this.user.can_publish
    },
    isAdmin() {
      return !!this.user && this.user.is_admin
    },
    initials() {
      return this.initialsOf(this.user || {})
    },
    canCreate() {
      return this.form.title.trim() && this.form.research_brief.trim()
    },
    createJob() {
      return this.jobs["create"]
    },
  },
  methods: {
    async api(path, opts = {}) {
      const res = await fetch("/api" + path, {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...opts,
      })
      if (!res.ok) throw new Error((await res.text()) || res.statusText)
      return res.status === 204 ? null : res.json()
    },

    /* ----------------------------- bootstrap ----------------------------- */
    async load() {
      try {
        const data = await this.api("/bootstrap")
        this.online = true
        this.user = data.user
        this.needsSetup = data.needs_setup
        if (data.user) localStorage.setItem("pdj_user", JSON.stringify(data.user))
        this.themes = data.themes
        this.languages = data.languages
        this.keys = data.keys
        this.schedules = data.schedules
        this.cron = data.cron
        this.duration = data.duration
        this.smtpConfigured = data.smtp_configured
        if (!this.loaded && data.languages.length) {
          this.form.minutes = data.duration.default
          this.form.language = (data.languages[0] || { code: "fr" }).code
          this.loaded = true
        }
        if (this.isAdmin && this.view === "admin") this.loadUsers()
      } catch (e) {
        // Offline (or server down): fall back to cached identity + saved episodes.
        this.online = false
        const cached = localStorage.getItem("pdj_user")
        if (cached) {
          this.user = JSON.parse(cached)
          this.view = "offline"
        }
      }
    },

    /* ------------------------------- auth -------------------------------- */
    toggleAuthMode() {
      this.authMode = this.authMode === "login" ? "register" : "login"
      this.authError = ""
    },
    async submitAuth() {
      this.authError = ""
      this.authBusy = true
      try {
        const path = this.authMode === "login" ? "/auth/login" : "/auth/register"
        const user = await this.api(path, { method: "POST", body: JSON.stringify(this.auth) })
        this.user = user
        localStorage.setItem("pdj_user", JSON.stringify(user))
        this.auth = { email: "", password: "", name: "" }
        await this.load()
      } catch (e) {
        this.authError = String(e.message || e).slice(0, 200)
      } finally {
        this.authBusy = false
      }
    },
    async logout() {
      try {
        await this.api("/auth/logout", { method: "POST" })
      } catch (_) {}
      localStorage.removeItem("pdj_user")
      this.user = null
      this.menuOpen = false
      this.view = "today"
    },

    /* --------------------------- subscriptions --------------------------- */
    async toggleSub(theme) {
      const next = !theme.subscribed
      try {
        await this.api("/subscriptions", { method: "POST", body: JSON.stringify({ theme_key: theme.key, subscribed: next }) })
        theme.subscribed = next
        this.flash(next ? (this.smtpConfigured ? "Abonné — notifications email activées" : "Abonné (email non configuré)") : "Désabonné")
      } catch (e) {
        this.flash("Erreur d'abonnement")
      }
    },

    /* ------------------------------- jobs -------------------------------- */
    busySlot(slot) {
      return !!this.jobs[slot] && this.jobs[slot].status === "running"
    },
    pollJob(slot, jobId, onDone) {
      const tick = async () => {
        let job
        try {
          job = await this.api("/jobs/" + jobId)
        } catch (e) {
          this.jobs[slot] = { status: "error", text: String(e) }
          return
        }
        this.jobs[slot] = { status: job.status, text: (job.log || []).join("\n") }
        if (job.status === "running") {
          setTimeout(tick, 1500)
        } else {
          if (job.status === "error") {
            this.flash("Échec de la génération")
            setTimeout(() => delete this.jobs[slot], 9000)
          } else {
            delete this.jobs[slot]
          }
          if (onDone) onDone(job)
        }
      }
      tick()
    },
    async generate(theme) {
      try {
        const { job } = await this.api("/generate", { method: "POST", body: JSON.stringify({ theme_key: theme.key, language: theme.language, minutes: theme.minutes }) })
        this.jobs["theme:" + theme.key] = { status: "running", text: "Démarrage…" }
        this.pollJob("theme:" + theme.key, job, () => this.load())
      } catch (e) {
        this.flash("Erreur : " + e.message)
      }
    },
    async doShare(ep) {
      try {
        const r = await this.api("/episodes/" + ep.id + "/share", { method: "POST" })
        ep.share_key = r.key
        try {
          await navigator.clipboard.writeText(location.origin + r.path)
          this.flash("Lien de partage copié")
        } catch (_) {
          this.flash("Lien de partage créé")
        }
      } catch (e) {
        this.flash("Erreur de partage")
      }
    },
    async doRegenerate({ episode, language }) {
      try {
        const { job } = await this.api("/episodes/" + episode.id + "/regenerate", { method: "POST", body: JSON.stringify({ language }) })
        this.jobs["ep:" + episode.id] = { status: "running", text: "Démarrage…" }
        this.pollJob("ep:" + episode.id, job, () => {
          this.load()
          this.refreshHistory()
        })
      } catch (e) {
        this.flash("Erreur : " + e.message)
      }
    },
    async doDelete(ep) {
      if (!confirm("Supprimer cet épisode ?")) return
      await this.api("/episodes/" + ep.id, { method: "DELETE" })
      this.flash("Épisode supprimé")
      this.load()
      this.refreshHistory()
    },

    /* ----------------------------- offline ------------------------------- */
    isSaved(id) {
      return this.saved.some((e) => e.id === id)
    },
    loadSaved() {
      try {
        this.saved = JSON.parse(localStorage.getItem("pdj_saved") || "[]")
      } catch (_) {
        this.saved = []
      }
    },
    async saveOffline(ep) {
      try {
        const cache = await caches.open("pdj-audio")
        await cache.add(ep.audio_url)
        const entry = {
          id: ep.id, theme_key: ep.theme_key, theme_title: ep.theme_title, icon: ep.icon, accent: ep.accent,
          title: ep.title, summary: ep.summary, date: ep.date, language: ep.language,
          language_label: ep.language_label, minutes: ep.minutes, audio_url: ep.audio_url,
        }
        this.saved = [entry, ...this.saved.filter((e) => e.id !== ep.id)]
        localStorage.setItem("pdj_saved", JSON.stringify(this.saved))
        this.flash("Enregistré pour écoute hors-ligne")
      } catch (e) {
        this.flash("Impossible d'enregistrer hors-ligne")
      }
    },
    async removeOffline(ep) {
      try {
        const cache = await caches.open("pdj-audio")
        await cache.delete(ep.audio_url)
      } catch (_) {}
      this.saved = this.saved.filter((e) => e.id !== ep.id)
      localStorage.setItem("pdj_saved", JSON.stringify(this.saved))
      this.flash("Retiré des épisodes hors-ligne")
    },

    /* ----------------------------- history ------------------------------- */
    async openHistory(theme) {
      this.history.theme = theme
      this.history.episodes = await this.api("/episodes?theme=" + theme.key + "&days=7")
      const dialog = this.$refs.historyDialog
      // Fallback light-dismiss for browsers without <dialog closedby> support.
      if (!this._dismissBound && !("closedBy" in HTMLDialogElement.prototype)) {
        this._dismissBound = true
        dialog.addEventListener("click", (event) => {
          if (event.target !== dialog) return
          const r = dialog.getBoundingClientRect()
          const inside = r.top <= event.clientY && event.clientY <= r.top + r.height && r.left <= event.clientX && event.clientX <= r.left + r.width
          if (!inside) dialog.close()
        })
      }
      dialog.showModal()
    },
    refreshHistory() {
      if (this.history.theme) {
        this.api("/episodes?theme=" + this.history.theme.key + "&days=7").then((e) => (this.history.episodes = e))
      }
    },
    closeHistory() {
      this.$refs.historyDialog.close()
    },

    /* ------------------------------ create ------------------------------- */
    async createTheme() {
      try {
        const r = await this.api("/custom-theme", { method: "POST", body: JSON.stringify({ ...this.form }) })
        if (r.job) {
          this.jobs["create"] = { status: "running", text: "Démarrage…" }
          this.pollJob("create", r.job, () => {
            this.load()
            this.view = "today"
          })
        }
        this.flash(r.schedule ? "Thématique créée et planifiée" : "Thématique créée")
        await this.load()
      } catch (e) {
        this.flash("Erreur de création : " + e.message)
      }
    },

    /* ---------------------------- admin/settings ------------------------- */
    async saveKeys() {
      const payload = {}
      for (const name in this.keyInputs) if ((this.keyInputs[name] || "").trim()) payload[name] = this.keyInputs[name].trim()
      this.keys = await this.api("/settings/keys", { method: "POST", body: JSON.stringify(payload) })
      this.keyInputs = {}
      this.flash("Clés enregistrées")
    },
    async installCron() {
      try {
        await this.api("/cron/install", { method: "POST" })
        this.cron.installed = true
        this.flash("Tâche cron installée")
      } catch (e) {
        this.flash("Impossible d'installer le cron")
      }
    },
    async uninstallCron() {
      await this.api("/cron/uninstall", { method: "POST" })
      this.cron.installed = false
      this.flash("Tâche cron retirée")
    },
    async toggleSchedule(s) {
      await this.api("/schedules/" + s.id + "/toggle", { method: "POST", body: JSON.stringify({ enabled: !s.enabled }) })
      s.enabled = !s.enabled
    },
    async deleteSchedule(s) {
      await this.api("/schedules/" + s.id, { method: "DELETE" })
      this.schedules = this.schedules.filter((x) => x.id !== s.id)
    },
    async loadUsers() {
      try {
        this.users = await this.api("/users")
      } catch (_) {}
    },
    async changeRole(u, role) {
      try {
        const updated = await this.api("/users/" + u.id + "/role", { method: "POST", body: JSON.stringify({ role }) })
        u.role = updated.role
        this.flash("Rôle mis à jour")
      } catch (e) {
        this.flash(e.message || "Erreur")
        this.loadUsers()
      }
    },
    async deleteUser(u) {
      if (!confirm(`Supprimer le compte ${u.email} ?`)) return
      try {
        await this.api("/users/" + u.id, { method: "DELETE" })
        this.users = this.users.filter((x) => x.id !== u.id)
        this.flash("Compte supprimé")
      } catch (e) {
        this.flash(e.message || "Erreur")
      }
    },

    /* ------------------------------ helpers ------------------------------ */
    themeTitle(key) {
      const t = this.themes.find((x) => x.key === key)
      return t ? t.title : key
    },
    roleLabel(role) {
      return { admin: "Admin", publisher: "Publisher", reader: "Reader" }[role] || role
    },
    initialsOf(u) {
      const base = (u.name || (u.email || "?").split("@")[0] || "?").trim()
      const parts = base.split(/\s+/)
      return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || base[0]?.toUpperCase() || "?"
    },
    flash(message) {
      this.toast = message
      clearTimeout(this._toastTimer)
      this._toastTimer = setTimeout(() => (this.toast = ""), 2600)
    },
  },
  watch: {
    view(v) {
      if (v === "admin" && this.isAdmin) this.loadUsers()
    },
  },
  mounted() {
    this.loadSaved()
    this.load()
    addEventListener("online", () => {
      this.online = true
      this.load()
    })
    addEventListener("offline", () => (this.online = false))
    addEventListener("click", (e) => {
      if (this.menuOpen && !e.target.closest(".acct")) this.menuOpen = false
    })
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {})
    }
  },
}).mount("#app")
