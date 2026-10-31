// French catalog (reference locale). Keys are flat dot-notation; {param}
// placeholders are interpolated by the t() function.
export const fr = {
  // --- Common ---
  'common.appName': 'FiscAI PreClear',
  'common.cancel': 'Annuler',
  'common.save': 'Enregistrer',
  'common.saving': 'Enregistrement…',
  'common.retry': 'Réessayer',
  'common.loading': 'Chargement…',
  'common.loadingPage': 'Chargement de la page…',
  'common.search': 'Recherche',
  'common.all': 'Tous',
  'common.allF': 'Toutes',
  'common.status': 'Statut',
  'common.type': 'Type',
  'common.severity': 'Sévérité',
  'common.actionLabel': 'Action',
  'common.recommendedAction': 'Action recommandée',
  'common.close': 'Fermer',
  'common.open': 'Ouvrir',
  'common.backHome': '← Retour à l’accueil',
  'common.optional': 'optionnel',
  'common.of100': '/100',

  // --- Disclaimer / privacy ---
  'legal.disclaimer':
    'FiscAI fournit une assistance au pré-contrôle fiscal et douanier. Les résultats doivent être vérifiés par un comptable, un transitaire ou un expert habilité avant tout usage officiel.',
  'legal.privacy':
    'Vos documents sont traités de manière confidentielle et ne sont jamais transmis à des tiers sans votre accord. FiscAI est un outil d’aide à la décision : aucune décision fiscale ou douanière officielle n’est prise sans revue humaine.',
  'legal.disclaimerPrefix': 'Avertissement : ',
  'legal.readOnly': 'Mode lecture seule activé pour protéger vos données.',

  // --- Navigation ---
  'nav.dashboard': 'Tableau de bord',
  'nav.dossiers': 'Dossiers',
  'nav.documents': 'Documents',
  'nav.agents': 'Agents IA',
  'nav.alerts': 'Alertes',
  'nav.expertReview': 'Revue experte',
  'nav.reports': 'Rapports',
  'nav.audit': 'Journal d’audit',
  'nav.settings': 'Paramètres',
  'nav.pricing': 'Tarifs',
  'nav.login': 'Se connecter',
  'nav.logout': 'Déconnexion',
  'nav.sidebarNote': 'Pré-contrôle IA — les résultats exigent une validation experte.',
  'nav.mainNav': 'Navigation principale',
  'nav.publicNav': 'Navigation publique',
  'nav.workspace': 'Espace de travail',

  // --- Roles / language ---
  'role.admin': 'admin',
  'role.analyst': 'analyste',
  'role.expert': 'expert',
  'role.viewer': 'lecteur',
  'lang.label': 'Langue de l’interface',
  'lang.fr': 'Français',
  'lang.en': 'English',

  // --- Risk levels ---
  'risk.low': 'Risque faible',
  'risk.medium': 'Risque moyen',
  'risk.high': 'Risque élevé',
  'risk.critical': 'Risque critique',
  'risk.scoreAria': 'score {score} sur 100',

  // --- Severity ---
  'severity.label': 'Sévérité : {value}',
  'severity.critical': 'Critique',
  'severity.high': 'Élevée',
  'severity.medium': 'Moyenne',
  'severity.low': 'Faible',

  // --- Dossier status ---
  'dossierStatus.draft': 'Brouillon',
  'dossierStatus.analyzing': 'Analyse en cours',
  'dossierStatus.analyzed': 'Analysé',
  'dossierStatus.needs_review': 'Revue requise',
  'dossierStatus.reviewed': 'Revu par expert',
  'dossierStatus.issue': 'Problème actif',

  // --- Dossier types ---
  'dossierType.import': 'Dossier Import',
  'dossierType.export': 'Dossier Export',
  'dossierType.fiscal': 'Dossier Fiscal / TVA',

  // --- Document types ---
  'docType.commercial_invoice': 'Facture commerciale',
  'docType.packing_list': 'Liste de colisage',
  'docType.transport_document': 'Document de transport',
  'docType.certificate_origin': 'Certificat d’origine',
  'docType.customs_declaration': 'Déclaration douanière',
  'docType.vat_declaration': 'Déclaration de TVA',
  'docType.other': 'Autre document',

  // --- Alert status ---
  'alertStatus.open': 'Ouverte',
  'alertStatus.in_review': 'En cours de revue',
  'alertStatus.resolved': 'Résolue',

  // --- Landing ---
  'landing.badge': 'Fiscalité · TVA · Douane — Maroc',
  'landing.heroTitle':
    'Pré-contrôlez vos dossiers fiscaux et douaniers avant qu’ils ne partent',
  'landing.heroSubtitle':
    'FiscAI PreClear analyse vos factures et dossiers import/export avec des agents IA, détecte les documents manquants et les incohérences TVA/douane, et prépare un rapport de risque — avant vos échanges avec comptables, transitaires, DGI, PortNet ou BADR.',
  'landing.ctaDemo': 'Essayer la démo',
  'landing.ctaPricing': 'Voir les tarifs',
  'landing.featuresAria': 'Fonctionnalités',
  'landing.f1.title': 'Pré-contrôle des dossiers',
  'landing.f1.text':
    'Analyse des factures, documents fiscaux et dossiers import/export avant transmission à vos comptables, transitaires et aux flux PortNet/BADR.',
  'landing.f2.title': 'Agents IA spécialisés',
  'landing.f2.text':
    'Agents fiscal, douane, réglementation, conformité et anomalies travaillent en pipeline, avec preuves et niveau de confiance.',
  'landing.f3.title': 'Score de risque',
  'landing.f3.text':
    'Scores fiscal et douanier 0-100, détection des documents manquants et incohérences TVA / code SH.',
  'landing.f4.title': 'Alertes et vigilance',
  'landing.f4.text':
    'Alertes hiérarchisées (critique → faible) avec suivi de statut jusqu’à résolution.',
  'landing.f5.title': 'Revue experte',
  'landing.f5.text':
    'Aucune conclusion officielle sans validation humaine : workflow de revue intégré et journalisé.',
  'landing.f6.title': 'Rapports prêts à transmettre',
  'landing.f6.text':
    'Rapports structurés (synthèse, constats, actions, piste d’audit) pour vos experts et partenaires.',
  'landing.footer':
    '© 2026 FiscAI PreClear — Outil d’aide à la décision. Ne remplace ni comptable, ni transitaire, ni administration fiscale ou douanière.',

  // --- Auth ---
  'auth.loginTitle': 'Connexion',
  'auth.demoHint': 'Compte démo : {email} / {password}',
  'auth.email': 'Adresse e-mail',
  'auth.emailPro': 'Adresse e-mail professionnelle',
  'auth.password': 'Mot de passe',
  'auth.passwordRule': 'Mot de passe (8 caractères min.)',
  'auth.loginCta': 'Se connecter',
  'auth.loggingIn': 'Connexion en cours…',
  'auth.noAccount': 'Pas de compte ?',
  'auth.createAccount': 'Créer un compte',
  'auth.registerTitle': 'Créer un compte',
  'auth.fullName': 'Nom complet',
  'auth.creating': 'Création du compte…',
  'auth.createCta': 'Créer mon compte',
  'auth.alreadyMember': 'Déjà inscrit ?',

  // --- Dashboard ---
  'dashboard.title': 'Tableau de bord',
  'dashboard.subtitle': 'Vue d’ensemble de vos pré-contrôles fiscaux et douaniers.',
  'dashboard.newDossier': 'Nouveau dossier',
  'dashboard.kpiDossiers': 'Dossiers actifs',
  'dashboard.kpiDossiersHint': 'Tous types confondus',
  'dashboard.kpiReview': 'En attente de revue experte',
  'dashboard.kpiReviewHint': 'Validation humaine requise',
  'dashboard.kpiAlerts': 'Alertes ouvertes',
  'dashboard.kpiAlertsHint': 'Critique → faible',
  'dashboard.kpiReports': 'Rapports générés',
  'dashboard.kpiReportsHint': 'Prêts à transmettre',
  'dashboard.recent': 'Dossiers récents',
  'dashboard.seeAll': 'Voir tous les dossiers',
  'dashboard.emptyTitle': 'Aucun dossier pour le moment',
  'dashboard.emptyDesc':
    'Créez votre premier dossier pour lancer un pré-contrôle fiscal ou douanier.',
  'dashboard.emptyCta': 'Créer un dossier',

  // --- Dossiers list ---
  'dossiers.title': 'Dossiers',
  'dossiers.subtitle': 'Recherchez, filtrez et suivez vos dossiers de pré-contrôle.',
  'dossiers.searchPlaceholder': 'Titre ou client…',
  'dossiers.sort': 'Tri',
  'dossiers.sortDesc': 'Plus récents d’abord',
  'dossiers.sortAsc': 'Plus anciens d’abord',
  'dossiers.emptyTitle': 'Aucun dossier trouvé',
  'dossiers.emptyFiltered': 'Aucun dossier ne correspond à vos filtres.',
  'dossiers.emptyDefault': 'Créez votre premier dossier de pré-contrôle.',
  'dossiers.updatedOn': 'Mis à jour le {date}',
  'dossiers.ref': 'Réf. {ref}',
  'dossiers.openAria': 'Ouvrir le dossier {title}',

  // --- New dossier ---
  'newDossier.title': 'Nouveau dossier',
  'newDossier.subtitle':
    'Créez un dossier, ajoutez les documents, puis lancez l’analyse IA de pré-contrôle.',
  'newDossier.typeLabel': 'Type de dossier *',
  'newDossier.titleLabel': 'Titre du dossier *',
  'newDossier.titlePlaceholder': 'Ex. Import composants électroniques — Shenzhen',
  'newDossier.clientLabel': 'Client / entité concernée *',
  'newDossier.clientPlaceholder': 'Ex. ElectroMaroc SARL',
  'newDossier.refLabel': 'Référence BADR / PortNet (optionnel)',
  'newDossier.refPlaceholder': 'Ex. BADR-2026-11842',
  'newDossier.descLabel': 'Description (optionnel)',
  'newDossier.descPlaceholder': 'Contexte, marchandises, échéances…',
  'newDossier.creating': 'Création…',
  'newDossier.submit': 'Créer le dossier',
  'newDossier.created': 'Dossier « {title} » créé.',

  // --- Dossier detail ---
  'dossier.back': 'Dossiers',
  'dossier.createdOn': 'créé le {date}',
  'dossier.documents': 'Documents ({count})',
  'dossier.noDocuments': 'Aucun document. Ajoutez au minimum la facture commerciale.',
  'dossier.deleteDocAria': 'Supprimer le document {name}',
  'dossier.launchAnalysis': 'Lancer l’analyse IA',
  'dossier.analyzing': 'Analyse en cours…',
  'dossier.analysisStep': 'Étape {index}/{total} — {agent}',
  'dossier.results': 'Constats',
  'dossier.checklist': 'Checklist',
  'dossier.questions': 'Questions fournisseur',
  'dossier.agents': 'Agents',
  'dossier.fiscalScore': 'Score fiscal',
  'dossier.customsScore': 'Score douanier',
  'dossier.global': 'Global',
  'dossier.lowConfidence':
    'Résultat à faible confiance : la qualité des documents limite la fiabilité de l’extraction. Vérification humaine indispensable.',
  'dossier.partial': 'Analyse partielle : des documents requis sont absents.',
  'dossier.noFindings': 'Aucune anomalie détectée. Dossier prêt pour revue.',
  'dossier.noAnalysis':
    'Aucune analyse pour l’instant. Ajoutez vos documents puis lancez l’analyse IA.',
  'dossier.noAnalysisRight':
    'Aucune analyse pour l’instant. Ajoutez vos documents puis lancez l’analyse IA.',
  'dossier.noQuestions': 'Aucune question à transmettre.',
  'dossier.generateReport': 'Générer le rapport',
  'dossier.generating': 'Génération…',
  'dossier.analysisDone': 'Analyse terminée : score global {score}/100.',
  'dossier.analysisFailed': 'L’analyse a échoué',
  'dossier.docSent': 'Document « {name} » envoyé.',
  'dossier.docDeleted': 'Document « {name} » supprimé.',
  'dossier.reportGenerated': 'Rapport généré.',
  'dossier.loadErrorTitle': 'Impossible de charger ce dossier',
  'dossier.backToDossiers': 'Retour aux dossiers',
  'dossier.confirmPartialTitle': 'Documents requis manquants',
  'dossier.confirmPartialBody':
    'La facture commerciale est absente du dossier. Vous pouvez lancer une analyse partielle, mais le score de risque sera dégradé et le résultat marqué à faible confiance.',
  'dossier.addDocuments': 'Ajouter des documents',
  'dossier.launchPartial': 'Lancer une analyse partielle',
  'dossier.deleteDocTitle': 'Supprimer ce document ?',
  'dossier.deleteDocBody':
    'Le document « {name} » sera retiré du dossier. Cette action est journalisée dans la piste d’audit.',
  'dossier.deleteConfirm': 'Supprimer définitivement',

  // --- Upload ---
  'upload.docType': 'Type de document',
  'upload.dropHint': 'Glissez-déposez un fichier ou',
  'upload.choose': 'Choisir un fichier',
  'upload.sending': 'Envoi en cours…',
  'upload.formats': 'PDF, PNG, JPG, XLSX, XML, DOCX — 10 Mo max. Envoi sécurisé et confidentiel.',
  'upload.selectAria': 'Sélectionner un document à envoyer',

  // --- Documents library ---
  'documents.title': 'Bibliothèque de documents',
  'documents.subtitle': 'Tous les documents envoyés dans votre espace de travail.',
  'documents.searchPlaceholder': 'Nom du fichier…',
  'documents.emptyTitle': 'Aucun document',
  'documents.emptyDesc': 'Les documents envoyés depuis vos dossiers apparaîtront ici.',
  'documents.colFile': 'Fichier',
  'documents.colType': 'Type',
  'documents.colSize': 'Taille',
  'documents.colUploaded': 'Envoyé le',
  'documents.colDossier': 'Dossier',
  'documents.tableCaption': 'Liste des documents de l’organisation',

  // --- Agents page ---
  'agents.title': 'Agents IA',
  'agents.subtitle':
    'Le pipeline agentique FiscAI : chaque agent est spécialisé, journalisé, et soumis à validation humaine pour les cas à risque.',
  'agents.idleAction': 'Lancez une analyse depuis un dossier pour activer cet agent.',
  'agents.queryTitle': 'Agent Requêtes de données (aperçu)',
  'agents.queryPlaceholder': "Ex. SELECT * FROM dossiers WHERE statut = 'needs_review'",
  'agents.queryLabel': 'Requête de données',
  'agents.queryTest': 'Tester la requête',
  'agents.queryChecking': 'Vérification…',
  'agent.confidence': 'Confiance : {value}%',
  'agent.evidence': 'Preuves / sources',
  'agent.status.idle': 'En attente',
  'agent.status.running': 'En cours',
  'agent.status.completed': 'Terminé',
  'agent.status.failed': 'Échec',
  'agent.status.needs_review': 'Revue humaine requise',

  // --- Alerts ---
  'alerts.title': 'Centre d’alertes',
  'alerts.subtitle':
    'Alertes générées par l’analyse IA, triées par sévérité. Traitez-les jusqu’à résolution.',
  'alerts.emptyTitle': 'Aucune alerte',
  'alerts.emptyDesc': 'Aucune alerte ne correspond à ces filtres. Bon signe !',
  'alerts.statusLabel': 'Statut : {value}',
  'alerts.seeDossier': 'Voir le dossier',
  'alerts.toReview': 'Passer en revue',
  'alerts.markResolved': 'Marquer résolue',
  'alerts.updated': 'Alerte « {title} » mise à jour ({status}).',

  // --- Expert review ---
  'review.title': 'Revue experte',
  'review.subtitle':
    'Validation humaine obligatoire des dossiers à risque élevé ou critique avant tout usage officiel.',
  'review.awaiting': 'En attente ({count})',
  'review.emptyTitle': 'Aucun dossier en attente',
  'review.emptyDesc': 'Les dossiers à risque élevé apparaîtront ici après analyse.',
  'review.recent': 'Revues récentes',
  'review.decision': 'Décision',
  'review.selectPrompt':
    'Sélectionnez un dossier en attente pour examiner les constats de l’IA.',
  'review.findingsCount': '{count} constat(s) IA',
  'review.decisionRequired': 'Décision *',
  'review.validated': 'Dossier validé — conforme pour transmission',
  'review.correction': 'Correction requise — retour au client',
  'review.rejected': 'Rejeté — dossier non exploitable',
  'review.commentLabel': 'Commentaire expert * (journalisé)',
  'review.commentPlaceholder': 'Justifiez votre décision pour la piste d’audit…',
  'review.submit': 'Enregistrer la revue',
  'review.saved': 'Revue enregistrée pour « {title} ».',
  'review.decisionValidated': 'Validé',
  'review.decisionCorrection': 'Correction requise',

  // --- Reports ---
  'reports.title': 'Rapports',
  'reports.subtitle':
    'Rapports de pré-contrôle générés, prêts à transmettre à vos experts.',
  'reports.emptyTitle': 'Aucun rapport généré',
  'reports.emptyDesc': 'Générez un rapport depuis la page d’analyse d’un dossier.',
  'reports.seeDossiers': 'Voir les dossiers',
  'reports.openAria': 'Ouvrir le rapport {title}',
  'reports.allReports': 'Tous les rapports',
  'reports.export': 'Exporter (texte)',
  'reports.exporting': 'Export…',
  'reports.exported': 'Rapport exporté.',
  'reports.notFound': 'Rapport introuvable',
  'report.heading': 'Rapport de pré-contrôle fiscal & douanier',
  'report.client': 'Client',

  // --- Pricing ---
  'pricing.heroTitle': 'Tarifs simples et transparents',
  'pricing.heroSubtitle':
    'Choisissez le plan adapté à votre volume de dossiers. Sans engagement, annulable à tout moment.',
  'pricing.recommended': 'Recommandé',
  'pricing.perMonth': '/mois',
  'pricing.start': 'Commencer',
  'pricing.contact': 'Nous contacter',
  'pricing.starter.name': 'Starter',
  'pricing.starter.desc': 'Pour les PME qui débutent avec l’import/export.',
  'pricing.pro.name': 'Pro',
  'pricing.pro.desc': 'Pour cabinets comptables et transitaires.',
  'pricing.enterprise.name': 'Enterprise',
  'pricing.enterprise.price': 'Sur devis',
  'pricing.enterprise.desc': 'Pour groupes, institutions et gros volumes.',
  'pricing.starter.f1': '10 dossiers / mois',
  'pricing.starter.f2': 'Analyse IA fiscale et douanière',
  'pricing.starter.f3': 'Alertes et checklist',
  'pricing.starter.f4': 'Rapports de pré-contrôle',
  'pricing.starter.f5': 'Support e-mail',
  'pricing.pro.f1': '60 dossiers / mois',
  'pricing.pro.f2': 'Multi-clients et multi-utilisateurs',
  'pricing.pro.f3': 'Revue experte intégrée',
  'pricing.pro.f4': 'Journal d’audit complet',
  'pricing.pro.f5': 'Support prioritaire',
  'pricing.enterprise.f1': 'Dossiers illimités',
  'pricing.enterprise.f2': 'Intégrations PortNet / BADR / SIMPL',
  'pricing.enterprise.f3': 'SSO et rôles avancés',
  'pricing.enterprise.f4': 'Hébergement dédié',
  'pricing.enterprise.f5': 'Accompagnement dédié',

  // --- Settings ---
  'settings.title': 'Paramètres',
  'settings.subtitle': 'Organisation, équipe et confidentialité.',
  'settings.orgSection': 'Organisation',
  'settings.orgName': 'Nom de l’organisation',
  'settings.city': 'Ville',
  'settings.iceplan': 'ICE : {ice} · Plan : {plan}',
  'settings.readonly': 'Seul un administrateur peut modifier ces paramètres.',
  'settings.saved': 'Paramètres enregistrés.',
  'settings.team': 'Équipe ({count})',
  'settings.privacy': 'Confidentialité',
  'settings.demoTitle': 'Mode démonstration (startup)',
  'settings.demoDesc':
    'Réinitialise l’espace de travail avec les données de démonstration (dossiers, alertes, journal d’audit). Utile avant une présentation CEED / investisseurs.',
  'settings.demoReset': 'Réinitialiser les données de démo',
  'settings.demoConfirmTitle': 'Réinitialiser l’espace de démonstration ?',
  'settings.demoConfirmBody':
    'Toutes les données créées pendant cette session seront remplacées par les données de démonstration d’origine.',
  'settings.demoResetDone': 'Espace de démonstration réinitialisé. Rechargement…',
  'settings.reset': 'Réinitialiser',

  // --- Audit ---
  'audit.title': 'Journal d’audit',
  'audit.subtitle':
    'Trace horodatée de toutes les actions importantes : connexions, dossiers, analyses, alertes, revues et exports.',
  'audit.emptyTitle': 'Journal vide',
  'audit.emptyDesc': 'Les actions apparaîtront ici au fur et à mesure.',
  'audit.colDate': 'Date',
  'audit.colUser': 'Utilisateur',
  'audit.colAction': 'Action',
  'audit.colDetails': 'Détails',
  'audit.colRisk': 'Risque',
  'audit.tableCaption': 'Journal d’audit de l’organisation',

  // --- Errors / states ---
  'error.title': 'Une erreur est survenue',
  'error.unknown': 'Erreur inconnue.',
  'error.boundaryTitle': 'Une erreur inattendue est survenue',
  'error.boundaryBody':
    'L’équipe technique a été notifiée. Vous pouvez recharger la page ou revenir au tableau de bord.',
  'error.boundaryCta': 'Revenir au tableau de bord',
  'error.unauthorizedTitle': 'Accès non autorisé',
  'error.unauthorizedBody':
    'Cette section requiert le rôle « {role} ». Contactez l’administrateur de votre organisation pour obtenir l’accès.',
  'notFound.title': 'Page introuvable',
  'notFound.body': 'L’adresse demandée n’existe pas ou n’est plus disponible.',
  'notFound.cta': 'Revenir au tableau de bord',

  // --- Toast / notifications ---
  'toast.notifications': 'Notifications',
  'toast.dismiss': 'Fermer la notification',

  // --- Pagination ---
  'pagination.summary': 'Page {page} sur {pages} — {total} élément(s)',
  'pagination.prev': 'Page précédente',
  'pagination.next': 'Page suivante',

  // --- Checklist statuses ---
  'check.passed': 'Conforme',
  'check.failed': 'Non conforme',
  'check.needs_review': 'Revue requise',
  'check.missing': 'Manquant',

  // --- Report (generated in the current UI locale) ---
  'report.section.executive_summary': 'Synthèse exécutive',
  'report.section.extracted_data': 'Données extraites',
  'report.section.fiscal_findings': 'Constats fiscaux',
  'report.section.customs_findings': 'Constats douaniers',
  'report.section.missing_documents': 'Documents manquants',
  'report.section.anomalies': 'Anomalies majeures',
  'report.section.recommended_actions': 'Actions recommandées',
  'report.section.expert_review': 'Statut revue experte',
  'report.section.audit_trail': 'Résumé de la piste d’audit',
  'report.section.disclaimer': 'Avertissement',
  'report.summary':
    'Dossier « {title} » ({type}) pour {client}. Score global : {overall}/100 (niveau {level}). Score fiscal : {fiscal}/100 — Score douanier : {customs}/100. {findings} point(s) de vigilance identifié(s). {reviewSentence}',
  'report.summary.reviewRequired': 'Une revue experte est requise avant tout usage officiel.',
  'report.summary.reviewOptional':
    'Aucune revue experte obligatoire, une vérification humaine reste recommandée.',
  'report.extracted.none': 'Aucun document analysable fourni.',
  'report.extracted.line': '[{type}] confiance {confidence}% — {fields}',
  'report.fiscal.none': 'Aucune anomalie fiscale détectée.',
  'report.customs.none': 'Aucune anomalie douanière détectée.',
  'report.missing.none': 'Tous les documents attendus sont présents.',
  'report.anomalies.none': 'Aucune anomalie majeure.',
  'report.actions.ready': 'Dossier prêt pour transmission au comptable / transitaire.',
  'report.expert.validated': 'Validé par un expert.',
  'report.expert.correction': 'Corrections demandées par l’expert.',
  'report.expert.pending': 'En attente de revue experte.',
  'report.expert.notRequired': 'Revue experte non requise pour ce niveau de risque.',
} as const;
