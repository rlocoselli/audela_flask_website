"""Extra i18n strings for the legal pages.

We keep these in a separate module to avoid bloating the main i18n.py file.
"""

LEGAL_TRANSLATIONS = {
    # ---------------------------------------------------------------------
    # French
    # ---------------------------------------------------------------------
    "fr": {
        "footer.notice": "Mentions légales",
        "footer.terms": "Conditions d’utilisation",
        "footer.privacy": "Politique de confidentialité",
        "footer.retention": "Conservation des données",
        "footer.cookies": "Politique cookies",

        "legal.last_updated": "Dernière mise à jour : {date}",

        "cookie.banner.text": "Nous utilisons uniquement des cookies essentiels au fonctionnement du site. Pour en savoir plus, consultez notre politique cookies.",
        "cookie.banner.learn_more": "En savoir plus",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Réinitialiser le choix cookies",
        "cookie.banner.reset_done": "Votre choix cookies a été réinitialisé. Rafraîchissez la page pour revoir le bandeau.",

        "legal.notice.title": "Mentions légales",
        "legal.notice.body_html": """
<h3>1. Éditeur du site</h3>
<p><strong>AUDELA</strong> (ci‑après « AUDELA »).<br>
Email : <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Téléphone : <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Adresse : <em>à compléter</em></p>

<h3>2. Hébergement</h3>
<p>Hébergeur : <em>à compléter</em> (nom, adresse, contact).</p>

<h3>3. Propriété intellectuelle</h3>
<p>Le contenu du site (textes, visuels, marques, logos, code, base de données) est protégé par le droit de la propriété intellectuelle. Toute reproduction, représentation ou réutilisation sans autorisation écrite préalable est interdite, sauf exceptions légales.</p>

<h3>4. Responsabilité</h3>
<p>AUDELA met en œuvre des moyens raisonnables pour assurer l’exactitude et la mise à jour des informations publiées, sans garantie d’exhaustivité. L’utilisation du site se fait sous la responsabilité de l’utilisateur.</p>

<h3>5. Contact</h3>
<p>Pour toute question, vous pouvez nous contacter à l’adresse : <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Conditions d’utilisation",
        "legal.terms.body_html": """
<h3>1. Objet</h3>
<p>Les présentes conditions d’utilisation définissent les règles d’accès et d’utilisation du site et, le cas échéant, de ses services en ligne (portail, outils BI/ERP, formulaires de contact, contenus). En accédant au site, vous acceptez ces conditions.</p>

<h3>2. Accès au service</h3>
<ul>
  <li>Le site est accessible gratuitement à titre informatif. Certains services peuvent nécessiter un compte (par exemple un portail) ou faire l’objet de conditions particulières.</li>
  <li>Vous vous engagez à fournir des informations exactes lorsque cela est demandé (ex. formulaire de contact).</li>
</ul>

<h3>3. Usage autorisé</h3>
<p>Vous vous engagez à utiliser le site de manière loyale et conforme aux lois en vigueur. Sont notamment interdits :</p>
<ul>
  <li>toute tentative d’accès non autorisé aux systèmes, aux comptes ou aux données ;</li>
  <li>toute extraction massive ou automatisée de contenus sans autorisation ;</li>
  <li>toute action portant atteinte à la sécurité, à la disponibilité ou à l’intégrité du site ;</li>
  <li>la mise en ligne ou la transmission de contenus illicites, malveillants ou portant atteinte aux droits de tiers.</li>
</ul>

<h3>4. Propriété intellectuelle</h3>
<p>Les contenus et éléments du site restent la propriété de leurs titulaires. Aucune cession de droits n’est accordée, sauf mention contraire explicite.</p>

<h3>5. Disponibilité</h3>
<p>AUDELA s’efforce d’assurer la disponibilité du site, mais ne garantit pas une disponibilité ininterrompue. Des opérations de maintenance ou des incidents peuvent entraîner des interruptions temporaires.</p>

<h3>6. Limitation de responsabilité</h3>
<p>Dans les limites autorisées par la loi, AUDELA ne saurait être tenue responsable des dommages indirects (perte de chance, perte de données, perte d’exploitation) liés à l’utilisation du site. L’utilisateur est responsable de ses équipements, de sa connexion et de la sécurité de ses identifiants.</p>

<h3>7. Liens externes</h3>
<p>Le site peut contenir des liens vers des sites tiers. AUDELA n’exerce aucun contrôle sur ces sites et décline toute responsabilité quant à leur contenu ou leurs pratiques.</p>

<h3>8. Modification des conditions</h3>
<p>AUDELA peut modifier les présentes conditions à tout moment. La version applicable est celle publiée sur le site à la date de consultation.</p>

<h3>9. Droit applicable</h3>
<p>Les présentes conditions sont régies par le droit français. En cas de litige, les tribunaux compétents seront ceux du ressort du siège de l’éditeur, sauf disposition impérative contraire.</p>
""",

        "legal.privacy.title": "Politique de confidentialité",
        "legal.privacy.body_html": """
<h3>1. Responsable du traitement</h3>
<p><strong>AUDELA</strong> est responsable du traitement des données personnelles collectées via ce site. Contact : <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Données traitées</h3>
<ul>
  <li><strong>Données de contact</strong> : nom, email, téléphone, message (lorsque vous nous écrivez).</li>
  <li><strong>Données de compte</strong> (si vous utilisez un portail) : identifiant, rôle, informations de profil.</li>
  <li><strong>Données techniques</strong> : journaux de connexion, adresse IP, identifiants techniques, pages consultées (dans la mesure nécessaire à la sécurité et au bon fonctionnement).</li>
  <li><strong>Contenus transmis</strong> : fichiers ou informations que vous choisissez de téléverser ou de saisir dans des formulaires.</li>
</ul>

<h3>3. Finalités et bases légales</h3>
<ul>
  <li><strong>Répondre à vos demandes</strong> (contact, démonstration, support) : consentement et/ou intérêt légitime.</li>
  <li><strong>Fournir le service</strong> (ex. accès au portail) : exécution d’un contrat ou de mesures précontractuelles.</li>
  <li><strong>Sécurité</strong> (prévention de la fraude, protection des comptes, détection d’incidents) : intérêt légitime.</li>
  <li><strong>Obligations légales</strong> (si applicables) : respect d’une obligation légale.</li>
</ul>

<h3>4. Destinataires</h3>
<p>Les données sont destinées aux équipes habilitées d’AUDELA et, si nécessaire, à ses prestataires techniques (hébergement, e‑mail, sauvegardes), agissant en tant que sous‑traitants. Les données peuvent être communiquées aux autorités lorsque la loi l’exige.</p>

<h3>5. Durées de conservation</h3>
<p>Nous conservons les données pendant la durée nécessaire aux finalités décrites ci‑dessus, puis nous les supprimons ou anonymisons. Une synthèse des durées usuelles est disponible sur la page <a href=\"/legal/retention\">Conservation des données</a>.</p>

<h3>6. Sécurité</h3>
<p>Nous mettons en œuvre des mesures techniques et organisationnelles adaptées : contrôle d’accès, journalisation, sauvegardes, chiffrement lorsque pertinent, et limitation des habilitations.</p>

<h3>7. Transferts hors Union européenne</h3>
<p>Lorsque des prestataires situés hors de l’UE sont utilisés, nous veillons à encadrer les transferts par des garanties appropriées (ex. clauses contractuelles types) conformément au RGPD.</p>

<h3>8. Vos droits</h3>
<p>Vous disposez des droits d’accès, de rectification, d’effacement, de limitation, d’opposition, ainsi que du droit à la portabilité lorsque applicable. Vous pouvez retirer votre consentement à tout moment lorsqu’il constitue la base légale du traitement.</p>
<p>Pour exercer vos droits : <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>. Nous pourrons demander un justificatif d’identité en cas de doute raisonnable.</p>

<h3>9. Réclamation</h3>
<p>Vous pouvez introduire une réclamation auprès de l’autorité de contrôle compétente, notamment la CNIL (France).</p>

<h3>10. Cookies</h3>
<p>Pour en savoir plus sur les cookies et traceurs utilisés, consultez notre <a href=\"/legal/cookies\">Politique cookies</a>.</p>
""",

        "legal.retention.title": "Conservation des données",
        "legal.retention.body_html": """
<p>Conformément au principe de limitation de la conservation, nous conservons les données personnelles pendant une durée proportionnée à la finalité poursuivie, puis nous les supprimons ou les anonymisons.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Catégorie de données</th>
      <th>Exemples</th>
      <th>Durée indicative</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Demandes de contact / prospects</td>
      <td>Nom, email, message</td>
      <td>Jusqu’à 3 ans après le dernier contact</td>
    </tr>
    <tr>
      <td>Comptes portail</td>
      <td>Identifiant, rôle, profil</td>
      <td>Pendant l’activité du compte, puis archivage limité (jusqu’à 3 ans) pour la gestion des litiges et la sécurité</td>
    </tr>
    <tr>
      <td>Journaux de connexion / sécurité</td>
      <td>IP, horodatage, événements</td>
      <td>Entre 6 et 12 mois selon les besoins de sécurité</td>
    </tr>
    <tr>
      <td>Contenus transmis</td>
      <td>Fichiers téléversés, formulaires</td>
      <td>Pendant la fourniture du service, puis suppression ; sauvegardes techniques pour une durée limitée</td>
    </tr>
    <tr>
      <td>Données de facturation (si applicables)</td>
      <td>Factures, paiements</td>
      <td>Conservation conforme aux obligations comptables et fiscales en vigueur</td>
    </tr>
    <tr>
      <td>Cookies / préférences</td>
      <td>Session, langue, choix cookies</td>
      <td>Session ou durée limitée ; préférences conservées au maximum quelques mois</td>
    </tr>
  </tbody>
</table>

<p>Ces durées peuvent être adaptées en fonction d’obligations légales, d’un contrat spécifique, ou pour la constatation, l’exercice ou la défense de droits en justice.</p>
""",

        "legal.cookies.title": "Politique cookies",
        "legal.cookies.body_html": """
<h3>1. Qu’est‑ce qu’un cookie ?</h3>
<p>Un cookie est un petit fichier texte déposé sur votre terminal (ordinateur, mobile) lors de la consultation d’un site. Il permet, par exemple, de mémoriser une session ou des préférences.</p>

<h3>2. Cookies utilisés sur ce site</h3>
<ul>
  <li><strong>Cookies strictement nécessaires</strong> : cookies de session, sécurité, et préférences indispensables au fonctionnement (ex. langue).</li>
  <li><strong>Mesure d’audience / traceurs</strong> : si nous activons des outils d’analyse, ils seront configurés conformément à la réglementation et, le cas échéant, soumis à votre consentement.</li>
</ul>

<h3>3. Gestion de vos choix</h3>
<p>Par défaut, nous n’utilisons que des cookies essentiels. Vous pouvez aussi configurer votre navigateur pour bloquer ou supprimer les cookies ; cela peut toutefois dégrader certaines fonctionnalités.</p>

<h3>4. Durées</h3>
<p>Les cookies essentiels expirent généralement à la fin de la session ou après une durée limitée. Lorsque des cookies de mesure d’audience sont utilisés, leur durée de vie est limitée (à titre indicatif, 13 mois pour certains traceurs) et les données associées sont conservées pour une durée maximale limitée.</p>

<h3>5. Contact</h3>
<p>Pour toute question : <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },

    # ---------------------------------------------------------------------
    # English
    # ---------------------------------------------------------------------
    "en": {
        "footer.notice": "Legal notice",
        "footer.terms": "Terms of use",
        "footer.privacy": "Privacy policy",
        "footer.retention": "Data retention",
        "footer.cookies": "Cookie policy",

        "legal.last_updated": "Last updated: {date}",

        "cookie.banner.text": "We only use essential cookies required to run the website. To learn more, read our cookie policy.",
        "cookie.banner.learn_more": "Learn more",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Reset cookie choice",
        "cookie.banner.reset_done": "Your cookie choice has been reset. Refresh the page to see the banner again.",

        "legal.notice.title": "Legal notice",
        "legal.notice.body_html": """
<h3>1. Website publisher</h3>
<p><strong>AUDELA</strong> ("AUDELA").<br>
Email: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Phone: <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Address: <em>to be completed</em></p>

<h3>2. Hosting</h3>
<p>Hosting provider: <em>to be completed</em> (name, address, contact).</p>

<h3>3. Intellectual property</h3>
<p>All content on this website (texts, visuals, trademarks, logos, code, databases) is protected by intellectual property laws. Any reproduction or reuse without prior written authorisation is prohibited, except where legally allowed.</p>

<h3>4. Liability</h3>
<p>AUDELA uses reasonable efforts to keep information accurate and up to date, without guaranteeing completeness. You use the website at your own risk.</p>

<h3>5. Contact</h3>
<p>For any question, contact: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Terms of use",
        "legal.terms.body_html": """
<h3>1. Purpose</h3>
<p>These Terms of Use set the rules for accessing and using this website and, where applicable, its online services (portal, BI/ERP tools, contact forms, content). By accessing the website, you agree to these terms.</p>

<h3>2. Access</h3>
<ul>
  <li>The website is available for informational purposes. Certain services may require an account (e.g., a portal) or specific contractual terms.</li>
  <li>You agree to provide accurate information when requested (e.g., contact form).</li>
</ul>

<h3>3. Acceptable use</h3>
<p>You agree to use the website lawfully and fairly. In particular, you must not:</p>
<ul>
  <li>attempt unauthorised access to systems, accounts or data;</li>
  <li>perform large-scale or automated extraction of content without permission;</li>
  <li>harm security, availability or integrity of the website;</li>
  <li>upload or transmit illegal or malicious content, or infringe third‑party rights.</li>
</ul>

<h3>4. Intellectual property</h3>
<p>Website content and components remain the property of their owners. No rights are transferred unless explicitly stated.</p>

<h3>5. Availability</h3>
<p>We aim to keep the website available but do not guarantee uninterrupted access. Maintenance and incidents may cause temporary interruptions.</p>

<h3>6. Limitation of liability</h3>
<p>To the extent permitted by law, AUDELA is not liable for indirect damages (loss of data, loss of profits, business interruption) related to website use. You are responsible for your devices, internet connection, and keeping credentials secure.</p>

<h3>7. External links</h3>
<p>The website may contain links to third‑party websites. AUDELA has no control over them and is not responsible for their content or practices.</p>

<h3>8. Changes</h3>
<p>We may update these terms at any time. The version published on the website on the day you consult it applies.</p>

<h3>9. Governing law</h3>
<p>These terms are governed by French law. Any dispute will be handled by the courts where the publisher is established, unless mandatory rules provide otherwise.</p>
""",

        "legal.privacy.title": "Privacy policy",
        "legal.privacy.body_html": """
<h3>1. Data controller</h3>
<p><strong>AUDELA</strong> is the data controller for personal data collected via this website. Contact: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Personal data we process</h3>
<ul>
  <li><strong>Contact data</strong>: name, email, phone, message (when you contact us).</li>
  <li><strong>Account data</strong> (if you use a portal): username, role, profile information.</li>
  <li><strong>Technical data</strong>: connection/security logs, IP address, technical identifiers, visited pages (to the extent necessary for security and proper operation).</li>
  <li><strong>Content you provide</strong>: files or information you upload or submit through forms.</li>
</ul>

<h3>3. Purposes and legal bases</h3>
<ul>
  <li><strong>Reply to your requests</strong> (contact, demo, support): consent and/or legitimate interests.</li>
  <li><strong>Provide the service</strong> (e.g., portal access): contract performance or pre‑contractual steps.</li>
  <li><strong>Security</strong> (fraud prevention, account protection, incident detection): legitimate interests.</li>
  <li><strong>Legal obligations</strong> (where applicable): compliance with a legal obligation.</li>
</ul>

<h3>4. Recipients</h3>
<p>Data is accessed by authorised AUDELA staff and, where needed, by technical service providers (hosting, email, backups) acting as processors. Data may be disclosed to authorities where required by law.</p>

<h3>5. Retention</h3>
<p>We keep personal data for as long as necessary for the purposes above and then delete or anonymise it. Typical retention periods are summarised on the <a href=\"/legal/retention\">Data retention</a> page.</p>

<h3>6. Security</h3>
<p>We implement appropriate technical and organisational measures: access control, logging, backups, encryption when relevant, and least‑privilege access.</p>

<h3>7. Transfers outside the EU</h3>
<p>If providers outside the EU are used, transfers are safeguarded with appropriate measures (e.g., Standard Contractual Clauses) in line with GDPR.</p>

<h3>8. Your rights</h3>
<p>You have rights of access, rectification, erasure, restriction, objection, and data portability where applicable. You can withdraw consent at any time where consent is the legal basis.</p>
<p>To exercise your rights: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>. We may request proof of identity where justified.</p>

<h3>9. Complaints</h3>
<p>You may lodge a complaint with your supervisory authority, including the CNIL (France) when relevant.</p>

<h3>10. Cookies</h3>
<p>See our <a href=\"/legal/cookies\">Cookie policy</a> for details about cookies and similar technologies used.</p>
""",

        "legal.retention.title": "Data retention",
        "legal.retention.body_html": """
<p>In line with the storage limitation principle, we retain personal data only for as long as necessary for the purpose, then delete or anonymise it.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Data category</th>
      <th>Examples</th>
      <th>Indicative retention</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Contact requests / leads</td>
      <td>Name, email, message</td>
      <td>Up to 3 years after last contact</td>
    </tr>
    <tr>
      <td>Portal accounts</td>
      <td>Username, role, profile</td>
      <td>While the account is active, then limited archiving (up to 3 years) for dispute management and security</td>
    </tr>
    <tr>
      <td>Connection / security logs</td>
      <td>IP, timestamps, events</td>
      <td>Between 6 and 12 months depending on security needs</td>
    </tr>
    <tr>
      <td>Submitted content</td>
      <td>Uploaded files, form data</td>
      <td>During service provision, then deleted; technical backups for a limited period</td>
    </tr>
    <tr>
      <td>Billing data (if applicable)</td>
      <td>Invoices, payments</td>
      <td>Retained according to applicable accounting and tax obligations</td>
    </tr>
    <tr>
      <td>Cookies / preferences</td>
      <td>Session, language, cookie choice</td>
      <td>Session or limited duration; preferences stored for at most a few months</td>
    </tr>
  </tbody>
</table>

<p>These periods may be adjusted due to legal obligations, specific contracts, or for the establishment, exercise or defence of legal claims.</p>
""",

        "legal.cookies.title": "Cookie policy",
        "legal.cookies.body_html": """
<h3>1. What is a cookie?</h3>
<p>A cookie is a small text file stored on your device (computer, mobile) when you visit a website. It can be used to keep a session active or remember preferences.</p>

<h3>2. Cookies used on this website</h3>
<ul>
  <li><strong>Strictly necessary cookies</strong>: session, security, and essential preferences (e.g., language).</li>
  <li><strong>Analytics / trackers</strong>: if we enable analytics tools, they will be configured in compliance with applicable rules and, where required, subject to your consent.</li>
</ul>

<h3>3. Managing your choices</h3>
<p>By default, we only use essential cookies. You can also configure your browser to block or delete cookies; this may reduce some functionality.</p>

<h3>4. Lifetimes</h3>
<p>Essential cookies generally expire at the end of the session or after a limited duration. Where analytics cookies are used, their lifetime is limited (indicatively, 13 months for some trackers) and related data is retained for a limited maximum duration.</p>

<h3>5. Contact</h3>
<p>Questions: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },

    # ---------------------------------------------------------------------
    # Portuguese
    # ---------------------------------------------------------------------
    "pt": {
        "footer.notice": "Aviso legal",
        "footer.terms": "Termos de uso",
        "footer.privacy": "Política de privacidade",
        "footer.retention": "Retenção de dados",
        "footer.cookies": "Política de cookies",

        "legal.last_updated": "Última atualização: {date}",

        "cookie.banner.text": "Usamos apenas cookies essenciais para o funcionamento do site. Para saber mais, consulte nossa política de cookies.",
        "cookie.banner.learn_more": "Saiba mais",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Redefinir escolha de cookies",
        "cookie.banner.reset_done": "Sua escolha de cookies foi redefinida. Atualize a página para ver o aviso novamente.",

        "legal.notice.title": "Aviso legal",
        "legal.notice.body_html": """
<h3>1. Editor do site</h3>
<p><strong>AUDELA</strong> ("AUDELA").<br>
Email: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Telefone: <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Endereço: <em>a completar</em></p>

<h3>2. Hospedagem</h3>
<p>Provedor de hospedagem: <em>a completar</em> (nome, endereço, contato).</p>

<h3>3. Propriedade intelectual</h3>
<p>O conteúdo do site (textos, imagens, marcas, logotipos, código, bases de dados) é protegido por leis de propriedade intelectual. Qualquer reprodução ou reutilização sem autorização prévia por escrito é proibida, salvo exceções legais.</p>

<h3>4. Responsabilidade</h3>
<p>A AUDELA emprega esforços razoáveis para manter as informações corretas e atualizadas, sem garantir exatidão ou completude. O uso do site é de responsabilidade do usuário.</p>

<h3>5. Contato</h3>
<p>Dúvidas: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Termos de uso",
        "legal.terms.body_html": """
<h3>1. Objetivo</h3>
<p>Estes Termos de Uso definem as regras de acesso e utilização do site e, quando aplicável, de seus serviços online (portal, ferramentas BI/ERP, formulários, conteúdo). Ao acessar o site, você concorda com estes termos.</p>

<h3>2. Acesso</h3>
<ul>
  <li>O site é disponibilizado para fins informativos. Alguns serviços podem exigir conta (por exemplo, portal) ou condições contratuais específicas.</li>
  <li>Você se compromete a fornecer informações corretas quando solicitado (ex.: formulário de contato).</li>
</ul>

<h3>3. Uso permitido</h3>
<p>Você deve utilizar o site de forma lícita e leal. Em especial, é proibido:</p>
<ul>
  <li>tentar acesso não autorizado a sistemas, contas ou dados;</li>
  <li>extrair conteúdo em grande escala ou de forma automatizada sem permissão;</li>
  <li>prejudicar a segurança, disponibilidade ou integridade do site;</li>
  <li>enviar conteúdo ilegal, malicioso ou que viole direitos de terceiros.</li>
</ul>

<h3>4. Propriedade intelectual</h3>
<p>O conteúdo e os componentes do site permanecem propriedade de seus titulares. Nenhum direito é transferido, salvo indicação expressa.</p>

<h3>5. Disponibilidade</h3>
<p>Buscamos manter o site disponível, mas não garantimos acesso ininterrupto. Manutenções e incidentes podem causar interrupções temporárias.</p>

<h3>6. Limitação de responsabilidade</h3>
<p>Na medida permitida por lei, a AUDELA não se responsabiliza por danos indiretos (perda de dados, perda de lucros, interrupção) relacionados ao uso do site. Você é responsável por seus dispositivos, conexão e segurança das credenciais.</p>

<h3>7. Links externos</h3>
<p>O site pode conter links para sites de terceiros. A AUDELA não controla esses sites e não se responsabiliza por seu conteúdo ou práticas.</p>

<h3>8. Alterações</h3>
<p>Podemos atualizar estes termos a qualquer momento. A versão publicada no site na data de consulta é a aplicável.</p>

<h3>9. Lei aplicável</h3>
<p>Estes termos são regidos pela lei francesa. Eventuais litígios serão tratados pelos tribunais competentes do local de estabelecimento do editor, salvo regras obrigatórias em sentido contrário.</p>
""",

        "legal.privacy.title": "Política de privacidade",
        "legal.privacy.body_html": """
<h3>1. Controlador</h3>
<p><strong>AUDELA</strong> é o controlador dos dados pessoais coletados por este site. Contato: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Dados tratados</h3>
<ul>
  <li><strong>Dados de contato</strong>: nome, email, telefone, mensagem (quando você nos contata).</li>
  <li><strong>Dados de conta</strong> (se usar um portal): usuário, função, informações de perfil.</li>
  <li><strong>Dados técnicos</strong>: logs de conexão/segurança, endereço IP, identificadores técnicos, páginas visitadas (na medida necessária para segurança e funcionamento).</li>
  <li><strong>Conteúdo fornecido</strong>: arquivos e informações enviados por você.</li>
</ul>

<h3>3. Finalidades e bases legais</h3>
<ul>
  <li><strong>Responder solicitações</strong> (contato, demo, suporte): consentimento e/ou interesse legítimo.</li>
  <li><strong>Fornecer o serviço</strong> (acesso ao portal): execução de contrato ou medidas pré-contratuais.</li>
  <li><strong>Segurança</strong> (prevenção de fraude, proteção de contas): interesse legítimo.</li>
  <li><strong>Obrigações legais</strong> (quando aplicável): cumprimento de obrigação legal.</li>
</ul>

<h3>4. Destinatários</h3>
<p>Os dados são acessados por equipes autorizadas da AUDELA e, quando necessário, por prestadores técnicos (hospedagem, email, backups) atuando como operadores. Dados podem ser compartilhados com autoridades quando exigido por lei.</p>

<h3>5. Retenção</h3>
<p>Conservamos os dados pelo tempo necessário às finalidades e depois os excluímos ou anonimamos. Consulte a página <a href=\"/legal/retention\">Retenção de dados</a> para prazos típicos.</p>

<h3>6. Segurança</h3>
<p>Aplicamos medidas técnicas e organizacionais adequadas: controle de acesso, registros, backups, criptografia quando pertinente, e mínimo privilégio.</p>

<h3>7. Transferências fora da UE</h3>
<p>Se utilizarmos prestadores fora da UE, adotamos garantias apropriadas (por exemplo, cláusulas contratuais padrão) conforme o RGPD.</p>

<h3>8. Seus direitos</h3>
<p>Você possui direitos de acesso, retificação, exclusão, limitação, oposição e portabilidade (quando aplicável). Você pode retirar seu consentimento a qualquer momento quando ele for a base legal.</p>
<p>Para exercer seus direitos: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>. Podemos solicitar comprovação de identidade em casos justificados.</p>

<h3>9. Reclamações</h3>
<p>Você pode apresentar reclamação à autoridade competente, incluindo a CNIL (França) quando aplicável.</p>

<h3>10. Cookies</h3>
<p>Veja a <a href=\"/legal/cookies\">Política de cookies</a> para detalhes.</p>
""",

        "legal.retention.title": "Retenção de dados",
        "legal.retention.body_html": """
<p>De acordo com o princípio de limitação de conservação, mantemos dados pessoais apenas pelo tempo necessário à finalidade e depois os excluímos ou anonimamos.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Categoria</th>
      <th>Exemplos</th>
      <th>Prazo indicativo</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Solicitações de contato / leads</td>
      <td>Nome, email, mensagem</td>
      <td>Até 3 anos após o último contato</td>
    </tr>
    <tr>
      <td>Contas do portal</td>
      <td>Usuário, função, perfil</td>
      <td>Enquanto a conta estiver ativa, depois arquivamento limitado (até 3 anos) para litígios e segurança</td>
    </tr>
    <tr>
      <td>Logs de conexão / segurança</td>
      <td>IP, horários, eventos</td>
      <td>Entre 6 e 12 meses conforme necessidades de segurança</td>
    </tr>
    <tr>
      <td>Conteúdo enviado</td>
      <td>Uploads, dados de formulários</td>
      <td>Durante a prestação do serviço e depois excluído; backups técnicos por período limitado</td>
    </tr>
    <tr>
      <td>Faturamento (se aplicável)</td>
      <td>Faturas, pagamentos</td>
      <td>Conforme obrigações contábeis e fiscais aplicáveis</td>
    </tr>
    <tr>
      <td>Cookies / preferências</td>
      <td>Sessão, idioma, escolha de cookies</td>
      <td>Sessão ou prazo limitado; preferências por no máximo alguns meses</td>
    </tr>
  </tbody>
</table>

<p>Esses prazos podem ser ajustados por obrigações legais, contrato específico ou para a defesa de direitos em processos.</p>
""",

        "legal.cookies.title": "Política de cookies",
        "legal.cookies.body_html": """
<h3>1. O que é um cookie?</h3>
<p>Cookie é um pequeno arquivo de texto armazenado no seu dispositivo quando você visita um site. Ele pode manter uma sessão ativa ou lembrar preferências.</p>

<h3>2. Cookies usados neste site</h3>
<ul>
  <li><strong>Cookies estritamente necessários</strong>: sessão, segurança e preferências essenciais (ex.: idioma).</li>
  <li><strong>Analytics / rastreadores</strong>: se ativarmos ferramentas de análise, elas serão configuradas de acordo com a regulamentação e, quando necessário, dependerão do seu consentimento.</li>
</ul>

<h3>3. Como gerenciar</h3>
<p>Por padrão, usamos apenas cookies essenciais. Você pode configurar o navegador para bloquear ou apagar cookies; isso pode reduzir funcionalidades.</p>

<h3>4. Duração</h3>
<p>Cookies essenciais expiram ao final da sessão ou após prazo limitado. Quando cookies de audiência forem usados, sua vida útil é limitada (por exemplo, 13 meses para alguns rastreadores) e os dados associados ficam retidos por prazo máximo limitado.</p>

<h3>5. Contato</h3>
<p>Dúvidas: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },

    # ---------------------------------------------------------------------
    # Spanish
    # ---------------------------------------------------------------------
    "es": {
        "footer.notice": "Aviso legal",
        "footer.terms": "Términos de uso",
        "footer.privacy": "Política de privacidad",
        "footer.retention": "Retención de datos",
        "footer.cookies": "Política de cookies",

        "legal.last_updated": "Última actualización: {date}",

        "cookie.banner.text": "Solo usamos cookies esenciales necesarias para el funcionamiento del sitio. Para saber más, consulte nuestra política de cookies.",
        "cookie.banner.learn_more": "Más información",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Restablecer elección de cookies",
        "cookie.banner.reset_done": "Se ha restablecido su elección de cookies. Actualice la página para volver a ver el aviso.",

        "legal.notice.title": "Aviso legal",
        "legal.notice.body_html": """
<h3>1. Titular del sitio</h3>
<p><strong>AUDELA</strong> ("AUDELA").<br>
Email: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Teléfono: <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Dirección: <em>por completar</em></p>

<h3>2. Alojamiento</h3>
<p>Proveedor de alojamiento: <em>por completar</em> (nombre, dirección, contacto).</p>

<h3>3. Propiedad intelectual</h3>
<p>El contenido del sitio (textos, imágenes, marcas, logotipos, código, bases de datos) está protegido por la normativa de propiedad intelectual. Queda prohibida su reproducción o reutilización sin autorización escrita previa, salvo excepciones legales.</p>

<h3>4. Responsabilidad</h3>
<p>AUDELA realiza esfuerzos razonables para mantener la información actualizada y correcta, sin garantizar su exhaustividad. El uso del sitio es responsabilidad del usuario.</p>

<h3>5. Contacto</h3>
<p>Consultas: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Términos de uso",
        "legal.terms.body_html": """
<h3>1. Objeto</h3>
<p>Estos Términos de uso regulan el acceso y uso del sitio y, cuando proceda, de sus servicios en línea (portal, herramientas BI/ERP, formularios, contenidos). Al acceder al sitio, usted acepta estos términos.</p>

<h3>2. Acceso</h3>
<ul>
  <li>El sitio se ofrece con fines informativos. Algunos servicios pueden requerir cuenta (por ejemplo, un portal) o condiciones contractuales específicas.</li>
  <li>Usted se compromete a facilitar información veraz cuando se le solicite (por ejemplo, formulario de contacto).</li>
</ul>

<h3>3. Uso permitido</h3>
<p>Debe utilizar el sitio de forma lícita y leal. En particular, queda prohibido:</p>
<ul>
  <li>intentar accesos no autorizados a sistemas, cuentas o datos;</li>
  <li>extraer contenidos de manera masiva o automatizada sin permiso;</li>
  <li>afectar a la seguridad, disponibilidad o integridad del sitio;</li>
  <li>subir o transmitir contenidos ilegales o maliciosos, o vulnerar derechos de terceros.</li>
</ul>

<h3>4. Propiedad intelectual</h3>
<p>Los contenidos y componentes del sitio siguen siendo propiedad de sus titulares. No se concede ningún derecho salvo indicación expresa.</p>

<h3>5. Disponibilidad</h3>
<p>Intentamos mantener el sitio disponible, pero no garantizamos un acceso ininterrumpido. El mantenimiento o incidentes pueden causar interrupciones temporales.</p>

<h3>6. Limitación de responsabilidad</h3>
<p>En la medida permitida por la ley, AUDELA no será responsable de daños indirectos (pérdida de datos, lucro cesante, interrupción) relacionados con el uso del sitio. Usted es responsable de sus equipos, conexión y seguridad de sus credenciales.</p>

<h3>7. Enlaces externos</h3>
<p>El sitio puede incluir enlaces a sitios de terceros. AUDELA no controla dichos sitios y no asume responsabilidad por su contenido o prácticas.</p>

<h3>8. Cambios</h3>
<p>Podemos actualizar estos términos en cualquier momento. Se aplicará la versión publicada en la fecha de consulta.</p>

<h3>9. Ley aplicable</h3>
<p>Estos términos se rigen por la ley francesa. Cualquier controversia se someterá a los tribunales competentes del lugar de establecimiento del editor, salvo normas imperativas en contrario.</p>
""",

        "legal.privacy.title": "Política de privacidad",
        "legal.privacy.body_html": """
<h3>1. Responsable del tratamiento</h3>
<p><strong>AUDELA</strong> es el responsable del tratamiento de los datos personales recogidos a través de este sitio. Contacto: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Datos tratados</h3>
<ul>
  <li><strong>Datos de contacto</strong>: nombre, email, teléfono, mensaje (cuando usted nos escribe).</li>
  <li><strong>Datos de cuenta</strong> (si utiliza un portal): usuario, rol, información de perfil.</li>
  <li><strong>Datos técnicos</strong>: registros de conexión/seguridad, IP, identificadores técnicos, páginas visitadas (en la medida necesaria para seguridad y funcionamiento).</li>
  <li><strong>Contenido aportado</strong>: archivos o información que usted cargue o envíe.</li>
</ul>

<h3>3. Finalidades y bases jurídicas</h3>
<ul>
  <li><strong>Responder a sus solicitudes</strong> (contacto, demo, soporte): consentimiento y/o interés legítimo.</li>
  <li><strong>Prestar el servicio</strong> (acceso al portal): ejecución de contrato o medidas precontractuales.</li>
  <li><strong>Seguridad</strong> (prevención de fraude, protección de cuentas): interés legítimo.</li>
  <li><strong>Obligaciones legales</strong> (cuando proceda): cumplimiento de una obligación legal.</li>
</ul>

<h3>4. Destinatarios</h3>
<p>Los datos son accesibles por el personal autorizado de AUDELA y, cuando sea necesario, por proveedores técnicos (hosting, correo, copias de seguridad) como encargados del tratamiento. Los datos pueden comunicarse a autoridades cuando la ley lo exija.</p>

<h3>5. Conservación</h3>
<p>Conservamos los datos el tiempo necesario para las finalidades y después los eliminamos o anonimizamos. Consulte la página <a href=\"/legal/retention\">Retención de datos</a> para plazos típicos.</p>

<h3>6. Seguridad</h3>
<p>Aplicamos medidas apropiadas: control de accesos, registros, copias de seguridad, cifrado cuando proceda y principio de mínimo privilegio.</p>

<h3>7. Transferencias fuera de la UE</h3>
<p>Si utilizamos proveedores fuera de la UE, aplicamos garantías adecuadas (por ejemplo, cláusulas contractuales tipo) conforme al RGPD.</p>

<h3>8. Sus derechos</h3>
<p>Usted tiene derecho de acceso, rectificación, supresión, limitación, oposición y portabilidad cuando proceda. Puede retirar su consentimiento en cualquier momento cuando sea la base jurídica.</p>
<p>Para ejercer sus derechos: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>. Podemos solicitar prueba de identidad en casos justificados.</p>

<h3>9. Reclamaciones</h3>
<p>Puede presentar una reclamación ante la autoridad de control competente, incluida la CNIL (Francia) cuando proceda.</p>

<h3>10. Cookies</h3>
<p>Consulte nuestra <a href=\"/legal/cookies\">Política de cookies</a> para más detalles.</p>
""",

        "legal.retention.title": "Retención de datos",
        "legal.retention.body_html": """
<p>De acuerdo con el principio de limitación del plazo de conservación, retenemos los datos personales solo el tiempo necesario para la finalidad y después los eliminamos o anonimizamos.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Categoría</th>
      <th>Ejemplos</th>
      <th>Plazo orientativo</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Solicitudes de contacto / leads</td>
      <td>Nombre, email, mensaje</td>
      <td>Hasta 3 años tras el último contacto</td>
    </tr>
    <tr>
      <td>Cuentas del portal</td>
      <td>Usuario, rol, perfil</td>
      <td>Mientras la cuenta esté activa y, después, archivo limitado (hasta 3 años) por seguridad y litigios</td>
    </tr>
    <tr>
      <td>Registros de conexión / seguridad</td>
      <td>IP, marcas de tiempo, eventos</td>
      <td>Entre 6 y 12 meses según necesidades de seguridad</td>
    </tr>
    <tr>
      <td>Contenido enviado</td>
      <td>Subidas, datos de formularios</td>
      <td>Durante la prestación del servicio; después, eliminación; copias técnicas por un período limitado</td>
    </tr>
    <tr>
      <td>Facturación (si procede)</td>
      <td>Facturas, pagos</td>
      <td>Según obligaciones contables y fiscales aplicables</td>
    </tr>
    <tr>
      <td>Cookies / preferencias</td>
      <td>Sesión, idioma, elección de cookies</td>
      <td>Sesión o período limitado; preferencias como máximo unos meses</td>
    </tr>
  </tbody>
</table>

<p>Estos plazos pueden ajustarse por obligaciones legales, contratos específicos o para la defensa de derechos.</p>
""",

        "legal.cookies.title": "Política de cookies",
        "legal.cookies.body_html": """
<h3>1. ¿Qué es una cookie?</h3>
<p>Una cookie es un pequeño archivo de texto almacenado en su dispositivo cuando visita un sitio web. Puede servir para mantener una sesión o recordar preferencias.</p>

<h3>2. Cookies utilizadas</h3>
<ul>
  <li><strong>Cookies estrictamente necesarias</strong>: sesión, seguridad y preferencias esenciales (por ejemplo, idioma).</li>
  <li><strong>Analítica / rastreadores</strong>: si activamos herramientas de analítica, se configurarán conforme a la normativa y, cuando proceda, requerirán su consentimiento.</li>
</ul>

<h3>3. Gestión</h3>
<p>Por defecto, solo usamos cookies esenciales. Puede configurar su navegador para bloquear o eliminar cookies, lo que puede reducir la funcionalidad.</p>

<h3>4. Duración</h3>
<p>Las cookies esenciales suelen caducar al final de la sesión o tras un plazo limitado. Si se usan cookies de analítica, su vida útil se limita (por ejemplo, 13 meses para algunos rastreadores) y los datos asociados se conservan durante un plazo máximo limitado.</p>

<h3>5. Contacto</h3>
<p>Consultas: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },

    # ---------------------------------------------------------------------
    # Italian
    # ---------------------------------------------------------------------
    "it": {
        "footer.notice": "Note legali",
        "footer.terms": "Termini d’uso",
        "footer.privacy": "Informativa privacy",
        "footer.retention": "Conservazione dei dati",
        "footer.cookies": "Cookie policy",

        "legal.last_updated": "Ultimo aggiornamento: {date}",

        "cookie.banner.text": "Utilizziamo solo cookie essenziali necessari al funzionamento del sito. Per saperne di più, consulta la cookie policy.",
        "cookie.banner.learn_more": "Scopri di più",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Reimposta scelta cookie",
        "cookie.banner.reset_done": "La tua scelta cookie è stata reimpostata. Aggiorna la pagina per rivedere il banner.",

        "legal.notice.title": "Note legali",
        "legal.notice.body_html": """
<h3>1. Editore del sito</h3>
<p><strong>AUDELA</strong> ("AUDELA").<br>
Email: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Telefono: <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Indirizzo: <em>da completare</em></p>

<h3>2. Hosting</h3>
<p>Provider di hosting: <em>da completare</em> (nome, indirizzo, contatto).</p>

<h3>3. Proprietà intellettuale</h3>
<p>I contenuti del sito (testi, immagini, marchi, loghi, codice, banche dati) sono protetti dalle leggi sulla proprietà intellettuale. È vietata qualsiasi riproduzione o riutilizzo senza previa autorizzazione scritta, salvo eccezioni di legge.</p>

<h3>4. Responsabilità</h3>
<p>AUDELA adotta misure ragionevoli per mantenere le informazioni accurate e aggiornate, senza garanzia di completezza. L’uso del sito avviene sotto la responsabilità dell’utente.</p>

<h3>5. Contatto</h3>
<p>Per domande: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Termini d’uso",
        "legal.terms.body_html": """
<h3>1. Oggetto</h3>
<p>I presenti Termini d’uso disciplinano l’accesso e l’utilizzo del sito e, se applicabile, dei relativi servizi online (portale, strumenti BI/ERP, moduli, contenuti). Accedendo al sito accetti questi termini.</p>

<h3>2. Accesso</h3>
<ul>
  <li>Il sito è disponibile a scopo informativo. Alcuni servizi possono richiedere un account (es. portale) o condizioni contrattuali specifiche.</li>
  <li>Ti impegni a fornire informazioni corrette quando richiesto (es. modulo contatti).</li>
</ul>

<h3>3. Uso consentito</h3>
<p>Devi utilizzare il sito in modo lecito e corretto. È vietato, in particolare:</p>
<ul>
  <li>tentare accessi non autorizzati a sistemi, account o dati;</li>
  <li>estrarre contenuti in modo massivo o automatizzato senza autorizzazione;</li>
  <li>compromettere la sicurezza, disponibilità o integrità del sito;</li>
  <li>caricare o trasmettere contenuti illegali o dannosi, o violare diritti di terzi.</li>
</ul>

<h3>4. Proprietà intellettuale</h3>
<p>Contenuti e componenti del sito restano di proprietà dei rispettivi titolari. Nessun diritto è trasferito salvo indicazione espressa.</p>

<h3>5. Disponibilità</h3>
<p>Ci impegniamo a mantenere il sito disponibile, ma non garantiamo un accesso ininterrotto. Manutenzione o incidenti possono causare interruzioni temporanee.</p>

<h3>6. Limitazione di responsabilità</h3>
<p>Nei limiti consentiti dalla legge, AUDELA non è responsabile per danni indiretti (perdita di dati, mancato guadagno, interruzione) legati all’uso del sito. Sei responsabile dei tuoi dispositivi, della connessione e della sicurezza delle credenziali.</p>

<h3>7. Link esterni</h3>
<p>Il sito può contenere link a siti di terzi. AUDELA non li controlla e non è responsabile per contenuti o pratiche di tali siti.</p>

<h3>8. Modifiche</h3>
<p>Possiamo aggiornare questi termini in qualsiasi momento. Fa fede la versione pubblicata alla data di consultazione.</p>

<h3>9. Legge applicabile</h3>
<p>Questi termini sono regolati dalla legge francese. Le controversie saranno sottoposte ai tribunali competenti del luogo di stabilimento dell’editore, salvo norme imperative diverse.</p>
""",

        "legal.privacy.title": "Informativa privacy",
        "legal.privacy.body_html": """
<h3>1. Titolare del trattamento</h3>
<p><strong>AUDELA</strong> è il titolare del trattamento dei dati personali raccolti tramite questo sito. Contatto: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Dati trattati</h3>
<ul>
  <li><strong>Dati di contatto</strong>: nome, email, telefono, messaggio.</li>
  <li><strong>Dati account</strong> (se usi un portale): username, ruolo, profilo.</li>
  <li><strong>Dati tecnici</strong>: log di connessione/sicurezza, IP, identificativi tecnici, pagine visitate (solo quanto necessario).</li>
  <li><strong>Contenuti forniti</strong>: file o informazioni caricati/inviati.</li>
</ul>

<h3>3. Finalità e basi giuridiche</h3>
<ul>
  <li><strong>Rispondere alle richieste</strong>: consenso e/o legittimo interesse.</li>
  <li><strong>Fornire il servizio</strong>: esecuzione del contratto o misure precontrattuali.</li>
  <li><strong>Sicurezza</strong>: legittimo interesse.</li>
  <li><strong>Obblighi di legge</strong> (se applicabili): adempimento di un obbligo legale.</li>
</ul>

<h3>4. Destinatari</h3>
<p>I dati sono accessibili al personale autorizzato di AUDELA e, se necessario, a fornitori tecnici (hosting, email, backup) in qualità di responsabili del trattamento. I dati possono essere comunicati alle autorità quando richiesto dalla legge.</p>

<h3>5. Conservazione</h3>
<p>Conserviamo i dati per il tempo necessario alle finalità e poi li cancelliamo o anonimizziamo. Vedi la pagina <a href=\"/legal/retention\">Conservazione dei dati</a> per i tempi tipici.</p>

<h3>6. Sicurezza</h3>
<p>Adottiamo misure adeguate: controllo accessi, log, backup, cifratura quando pertinente, e principio del minimo privilegio.</p>

<h3>7. Trasferimenti extra UE</h3>
<p>Se utilizziamo fornitori fuori dall’UE, adottiamo garanzie adeguate (es. clausole contrattuali standard) in conformità al GDPR.</p>

<h3>8. Diritti</h3>
<p>Hai diritto di accesso, rettifica, cancellazione, limitazione, opposizione e portabilità (se applicabile). Puoi revocare il consenso in qualsiasi momento quando il consenso è la base giuridica.</p>
<p>Per esercitare i diritti: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>9. Reclami</h3>
<p>Puoi presentare reclamo all’autorità di controllo competente, inclusa la CNIL (Francia) quando pertinente.</p>

<h3>10. Cookie</h3>
<p>Consulta la <a href=\"/legal/cookies\">Cookie policy</a> per maggiori dettagli.</p>
""",

        "legal.retention.title": "Conservazione dei dati",
        "legal.retention.body_html": """
<p>In linea con il principio di limitazione della conservazione, tratteniamo i dati personali solo per il tempo necessario e poi li cancelliamo o anonimizziamo.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Categoria</th>
      <th>Esempi</th>
      <th>Durata indicativa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Richieste di contatto / lead</td>
      <td>Nome, email, messaggio</td>
      <td>Fino a 3 anni dall’ultimo contatto</td>
    </tr>
    <tr>
      <td>Account portale</td>
      <td>Username, ruolo, profilo</td>
      <td>Durante l’attività dell’account, poi archiviazione limitata (fino a 3 anni) per sicurezza e contenzioso</td>
    </tr>
    <tr>
      <td>Log di connessione / sicurezza</td>
      <td>IP, timestamp, eventi</td>
      <td>Tra 6 e 12 mesi in base alle esigenze di sicurezza</td>
    </tr>
    <tr>
      <td>Contenuti inviati</td>
      <td>Upload, dati moduli</td>
      <td>Durante il servizio e poi cancellati; backup tecnici per un periodo limitato</td>
    </tr>
    <tr>
      <td>Fatturazione (se applicabile)</td>
      <td>Fatture, pagamenti</td>
      <td>Secondo gli obblighi contabili e fiscali applicabili</td>
    </tr>
    <tr>
      <td>Cookie / preferenze</td>
      <td>Sessione, lingua, scelta cookie</td>
      <td>Sessione o durata limitata; preferenze per al massimo alcuni mesi</td>
    </tr>
  </tbody>
</table>

<p>Le durate possono essere adattate per obblighi di legge, contratti specifici o per la tutela di diritti in giudizio.</p>
""",

        "legal.cookies.title": "Cookie policy",
        "legal.cookies.body_html": """
<h3>1. Cosa sono i cookie?</h3>
<p>I cookie sono piccoli file di testo memorizzati sul dispositivo quando visiti un sito. Possono mantenere una sessione o ricordare preferenze.</p>

<h3>2. Cookie utilizzati</h3>
<ul>
  <li><strong>Cookie strettamente necessari</strong>: sessione, sicurezza e preferenze essenziali (es. lingua).</li>
  <li><strong>Analytics / tracker</strong>: se attiviamo strumenti di analisi, saranno configurati secondo la normativa e, se richiesto, soggetti al tuo consenso.</li>
</ul>

<h3>3. Gestione</h3>
<p>Di default usiamo solo cookie essenziali. Puoi configurare il browser per bloccare o eliminare i cookie; ciò può ridurre alcune funzionalità.</p>

<h3>4. Durata</h3>
<p>I cookie essenziali scadono a fine sessione o dopo un periodo limitato. Se vengono usati cookie di analisi, la loro durata è limitata (ad esempio 13 mesi per alcuni tracker) e i dati correlati sono conservati per un periodo massimo limitato.</p>

<h3>5. Contatto</h3>
<p>Domande: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },

    # ---------------------------------------------------------------------
    # German
    # ---------------------------------------------------------------------
    "de": {
        "footer.notice": "Impressum",
        "footer.terms": "Nutzungsbedingungen",
        "footer.privacy": "Datenschutzerklärung",
        "footer.retention": "Speicherdauer",
        "footer.cookies": "Cookie-Richtlinie",

        "legal.last_updated": "Zuletzt aktualisiert: {date}",

        "cookie.banner.text": "Wir verwenden nur notwendige Cookies, die für den Betrieb der Website erforderlich sind. Mehr dazu in unserer Cookie-Richtlinie.",
        "cookie.banner.learn_more": "Mehr erfahren",
        "cookie.banner.accept": "OK",
        "cookie.banner.reset": "Cookie-Auswahl zurücksetzen",
        "cookie.banner.reset_done": "Ihre Cookie-Auswahl wurde zurückgesetzt. Aktualisieren Sie die Seite, um das Banner erneut zu sehen.",

        "legal.notice.title": "Impressum",
        "legal.notice.body_html": """
<h3>1. Anbieter</h3>
<p><strong>AUDELA</strong> ("AUDELA").<br>
E-Mail: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a><br>
Telefon: <a href=\"tel:+33764142031\">+33 07 64 14 20 31</a><br>
Anschrift: <em>zu ergänzen</em></p>

<h3>2. Hosting</h3>
<p>Hosting-Anbieter: <em>zu ergänzen</em> (Name, Anschrift, Kontakt).</p>

<h3>3. Urheberrecht</h3>
<p>Die Inhalte der Website (Texte, Bilder, Marken, Logos, Code, Datenbanken) sind urheberrechtlich geschützt. Jede Vervielfältigung oder Weiterverwendung ohne vorherige schriftliche Zustimmung ist untersagt, sofern keine gesetzlichen Ausnahmen gelten.</p>

<h3>4. Haftung</h3>
<p>AUDELA bemüht sich, Informationen korrekt und aktuell zu halten, übernimmt jedoch keine Gewähr für Vollständigkeit. Die Nutzung erfolgt auf eigenes Risiko.</p>

<h3>5. Kontakt</h3>
<p>Fragen: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",

        "legal.terms.title": "Nutzungsbedingungen",
        "legal.terms.body_html": """
<h3>1. Gegenstand</h3>
<p>Diese Nutzungsbedingungen regeln den Zugriff auf und die Nutzung dieser Website sowie ggf. ihrer Online-Dienste (Portal, BI/ERP-Tools, Kontaktformulare, Inhalte). Durch den Zugriff akzeptieren Sie diese Bedingungen.</p>

<h3>2. Zugriff</h3>
<ul>
  <li>Die Website dient Informationszwecken. Bestimmte Dienste können ein Konto (z. B. Portal) oder gesonderte Vertragsbedingungen erfordern.</li>
  <li>Sie verpflichten sich, bei Bedarf korrekte Angaben zu machen (z. B. im Kontaktformular).</li>
</ul>

<h3>3. Zulässige Nutzung</h3>
<p>Sie nutzen die Website rechtmäßig und fair. Insbesondere ist untersagt:</p>
<ul>
  <li>unbefugte Zugriffsversuche auf Systeme, Konten oder Daten;</li>
  <li>massives oder automatisiertes Auslesen von Inhalten ohne Erlaubnis;</li>
  <li>Beeinträchtigung von Sicherheit, Verfügbarkeit oder Integrität der Website;</li>
  <li>Hochladen oder Übermitteln rechtswidriger oder schädlicher Inhalte bzw. Verletzung von Rechten Dritter.</li>
</ul>

<h3>4. Geistiges Eigentum</h3>
<p>Inhalte und Bestandteile der Website bleiben Eigentum der jeweiligen Rechteinhaber. Es werden keine Rechte übertragen, sofern nicht ausdrücklich angegeben.</p>

<h3>5. Verfügbarkeit</h3>
<p>Wir bemühen uns um Verfügbarkeit, garantieren jedoch keinen unterbrechungsfreien Zugriff. Wartung oder Störungen können zu temporären Ausfällen führen.</p>

<h3>6. Haftungsbeschränkung</h3>
<p>Soweit gesetzlich zulässig, haftet AUDELA nicht für indirekte Schäden (Datenverlust, entgangener Gewinn, Betriebsunterbrechung) im Zusammenhang mit der Nutzung. Sie sind für Geräte, Verbindung und die Sicherheit Ihrer Zugangsdaten verantwortlich.</p>

<h3>7. Externe Links</h3>
<p>Die Website kann Links zu Drittseiten enthalten. AUDELA hat darauf keinen Einfluss und übernimmt keine Verantwortung für Inhalte oder Praktiken dieser Seiten.</p>

<h3>8. Änderungen</h3>
<p>Wir können diese Bedingungen jederzeit ändern. Es gilt die Version, die am Tag Ihres Besuchs veröffentlicht ist.</p>

<h3>9. Anwendbares Recht</h3>
<p>Diese Bedingungen unterliegen französischem Recht. Streitigkeiten werden vor den zuständigen Gerichten am Sitz des Anbieters verhandelt, sofern zwingende Vorschriften nichts anderes bestimmen.</p>
""",

        "legal.privacy.title": "Datenschutzerklärung",
        "legal.privacy.body_html": """
<h3>1. Verantwortlicher</h3>
<p><strong>AUDELA</strong> ist Verantwortlicher für die über diese Website erhobenen personenbezogenen Daten. Kontakt: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>2. Verarbeitete Daten</h3>
<ul>
  <li><strong>Kontaktdaten</strong>: Name, E-Mail, Telefon, Nachricht.</li>
  <li><strong>Kontodaten</strong> (bei Portalnutzung): Benutzername, Rolle, Profilinformationen.</li>
  <li><strong>Technische Daten</strong>: Verbindungs-/Sicherheitslogs, IP-Adresse, technische Kennungen, besuchte Seiten (soweit für Sicherheit und Betrieb erforderlich).</li>
  <li><strong>Bereitgestellte Inhalte</strong>: Dateien oder Informationen, die Sie hochladen oder über Formulare senden.</li>
</ul>

<h3>3. Zwecke und Rechtsgrundlagen</h3>
<ul>
  <li><strong>Anfragen beantworten</strong> (Kontakt, Demo, Support): Einwilligung und/oder berechtigtes Interesse.</li>
  <li><strong>Dienst bereitstellen</strong> (Portalzugang): Vertragserfüllung oder vorvertragliche Maßnahmen.</li>
  <li><strong>Sicherheit</strong> (Betrugsprävention, Kontoschutz): berechtigtes Interesse.</li>
  <li><strong>Gesetzliche Pflichten</strong> (falls anwendbar): rechtliche Verpflichtung.</li>
</ul>

<h3>4. Empfänger</h3>
<p>Daten werden von autorisierten AUDELA-Mitarbeitenden verarbeitet und ggf. von technischen Dienstleistern (Hosting, E-Mail, Backups) als Auftragsverarbeiter. Eine Weitergabe an Behörden erfolgt nur, wenn gesetzlich erforderlich.</p>

<h3>5. Speicherdauer</h3>
<p>Wir speichern Daten nur so lange wie für die genannten Zwecke erforderlich und löschen oder anonymisieren sie anschließend. Übliche Speicherdauern finden Sie auf der Seite <a href=\"/legal/retention\">Speicherdauer</a>.</p>

<h3>6. Sicherheit</h3>
<p>Wir setzen angemessene technische und organisatorische Maßnahmen ein: Zugriffskontrollen, Protokollierung, Backups, Verschlüsselung soweit sinnvoll, und Prinzip der geringsten Privilegien.</p>

<h3>7. Übermittlungen außerhalb der EU</h3>
<p>Bei Einsatz von Dienstleistern außerhalb der EU werden geeignete Garantien (z. B. Standardvertragsklauseln) gemäß DSGVO verwendet.</p>

<h3>8. Ihre Rechte</h3>
<p>Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung, Widerspruch sowie Datenübertragbarkeit (soweit anwendbar). Eine Einwilligung können Sie jederzeit widerrufen, sofern Einwilligung die Rechtsgrundlage ist.</p>
<p>Zur Ausübung Ihrer Rechte: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>

<h3>9. Beschwerden</h3>
<p>Sie können sich bei der zuständigen Aufsichtsbehörde beschweren, einschließlich der CNIL (Frankreich) sofern relevant.</p>

<h3>10. Cookies</h3>
<p>Details finden Sie in unserer <a href=\"/legal/cookies\">Cookie-Richtlinie</a>.</p>
""",

        "legal.retention.title": "Speicherdauer",
        "legal.retention.body_html": """
<p>Im Sinne des Grundsatzes der Speicherbegrenzung bewahren wir personenbezogene Daten nur so lange auf, wie es für den Zweck erforderlich ist, und löschen oder anonymisieren sie danach.</p>

<table class=\"legal-table\">
  <thead>
    <tr>
      <th>Kategorie</th>
      <th>Beispiele</th>
      <th>Richtwert</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Kontaktanfragen / Leads</td>
      <td>Name, E-Mail, Nachricht</td>
      <td>Bis zu 3 Jahre nach dem letzten Kontakt</td>
    </tr>
    <tr>
      <td>Portalkonten</td>
      <td>Benutzername, Rolle, Profil</td>
      <td>Während das Konto aktiv ist, danach begrenzte Archivierung (bis zu 3 Jahre) für Sicherheit und Rechtsstreitigkeiten</td>
    </tr>
    <tr>
      <td>Verbindungs-/Sicherheitslogs</td>
      <td>IP, Zeitstempel, Ereignisse</td>
      <td>Zwischen 6 und 12 Monaten je nach Sicherheitsbedarf</td>
    </tr>
    <tr>
      <td>Übermittelte Inhalte</td>
      <td>Uploads, Formulardaten</td>
      <td>Während der Leistungserbringung, danach gelöscht; technische Backups für begrenzte Zeit</td>
    </tr>
    <tr>
      <td>Abrechnung (falls anwendbar)</td>
      <td>Rechnungen, Zahlungen</td>
      <td>Gemäß anwendbaren steuerlichen und buchhalterischen Pflichten</td>
    </tr>
    <tr>
      <td>Cookies / Einstellungen</td>
      <td>Sitzung, Sprache, Cookie-Auswahl</td>
      <td>Sitzung oder begrenzte Dauer; Einstellungen maximal einige Monate</td>
    </tr>
  </tbody>
</table>

<p>Diese Fristen können aufgrund gesetzlicher Pflichten, besonderer Verträge oder zur Durchsetzung/Verteidigung von Rechtsansprüchen angepasst werden.</p>
""",

        "legal.cookies.title": "Cookie-Richtlinie",
        "legal.cookies.body_html": """
<h3>1. Was sind Cookies?</h3>
<p>Cookies sind kleine Textdateien, die beim Besuch einer Website auf Ihrem Gerät gespeichert werden. Sie können z. B. eine Sitzung aufrechterhalten oder Einstellungen speichern.</p>

<h3>2. Verwendete Cookies</h3>
<ul>
  <li><strong>Unbedingt erforderliche Cookies</strong>: Sitzung, Sicherheit und notwendige Einstellungen (z. B. Sprache).</li>
  <li><strong>Analyse/Tracker</strong>: Falls wir Analyse-Tools aktivieren, werden diese gemäß den geltenden Vorschriften konfiguriert und – falls erforderlich – nur mit Ihrer Einwilligung gesetzt.</li>
</ul>

<h3>3. Verwaltung</h3>
<p>Standardmäßig verwenden wir nur notwendige Cookies. Sie können Ihren Browser so einstellen, dass Cookies blockiert oder gelöscht werden; dadurch können Funktionen eingeschränkt sein.</p>

<h3>4. Laufzeiten</h3>
<p>Notwendige Cookies laufen typischerweise am Ende der Sitzung oder nach begrenzter Zeit ab. Wenn Analyse-Cookies verwendet werden, ist deren Laufzeit begrenzt (z. B. 13 Monate für bestimmte Tracker) und die zugehörigen Daten werden nur für eine begrenzte maximale Dauer gespeichert.</p>

<h3>5. Kontakt</h3>
<p>Fragen: <a href=\"mailto:admin@audeladedonees.fr\">admin@audeladedonees.fr</a>.</p>
""",
    },
}
