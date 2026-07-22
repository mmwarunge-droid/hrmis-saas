import { Link } from 'react-router-dom';

const COMPANY = {
  platform: 'Ace',
  legalEntity: 'Ace HRMIS Platform',
  contactEmail: 'privacy@acehr.app',
  supportEmail: 'support@acehr.app',
  address: 'Nairobi, Kenya',
  effectiveDate: '18 May 2026',
};

function LegalLayout({ title, subtitle, children }) {
  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 via-slate-50 to-white px-4 py-10 text-slate-900">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 rounded-[2rem] border border-slate-200 bg-white p-8 shadow-xl shadow-blue-950/10">
          <Link
            to="/login"
            className="text-4xl font-semibold tracking-tight text-blue-950"
          >
            ace
          </Link>

          <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-blue-600">
            Legal Information
          </p>

          <h1 className="mt-4 text-3xl font-semibold text-slate-950">
            {title}
          </h1>

          {subtitle ? (
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              {subtitle}
            </p>
          ) : null}

          <p className="mt-4 text-sm text-slate-500">
            Effective date: {COMPANY.effectiveDate}
          </p>
        </header>

        <article className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-xl shadow-blue-950/10">
          <div className="prose prose-slate max-w-none">{children}</div>
        </article>

        <footer className="mt-8 flex flex-col items-center justify-between gap-4 px-2 text-sm text-slate-500 sm:flex-row">
          <div className="flex flex-wrap gap-4">
            <Link className="hover:text-blue-700" to="/privacy-policy">
              Privacy Policy
            </Link>
            <span>·</span>
            <Link className="hover:text-blue-700" to="/terms-of-service">
              Terms of Service
            </Link>
          </div>

          <p className="font-semibold tracking-tight text-slate-400">ace</p>
        </footer>
      </div>
    </main>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-xl font-semibold text-slate-950">{title}</h2>
      <div className="space-y-3 text-sm leading-7 text-slate-700">
        {children}
      </div>
    </section>
  );
}

function BulletList({ items }) {
  return (
    <ul className="ml-5 list-disc space-y-2">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalLayout
      title="Privacy Policy"
      subtitle="This Privacy Policy explains how Ace collects, uses, stores, protects, shares, and retains personal data processed through the Ace HRMIS platform."
    >
      <Section title="1. Introduction">
        <p>
          {COMPANY.platform} is a consulting-led human resource management
          information system used by organisations to manage HR records,
          employee profiles, documents, leave, attendance, onboarding workflows,
          compliance records, and related HR administration.
        </p>
        <p>
          This Privacy Policy applies to users of the Ace platform, including
          platform administrators, client administrators, managers, employees,
          consultants, and authorised support users.
        </p>
      </Section>

      <Section title="2. Who We Are">
        <p>
          For purposes of this policy, “Ace”, “we”, “our”, or “us” refers to{' '}
          {COMPANY.legalEntity}. Our contact details are:
        </p>
        <BulletList
          items={[
            `Email: ${COMPANY.contactEmail}`,
            `Support: ${COMPANY.supportEmail}`,
            `Address: ${COMPANY.address}`,
          ]}
        />
      </Section>

      <Section title="3. Our Role as Data Processor and Data Controller">
        <p>
          Ace may act as a data processor when it processes employee and HR data
          on behalf of a client organisation using the platform. In that case,
          the client organisation is normally the data controller and determines
          the purpose and means of processing.
        </p>
        <p>
          Ace may act as a data controller for account administration,
          billing, security, platform analytics, support communications,
          service improvement, legal compliance, and platform operations.
        </p>
      </Section>

      <Section title="4. Personal Data We Collect">
        <p>
          Depending on your role and how your organisation uses Ace, we may
          process the following categories of data:
        </p>
        <BulletList
          items={[
            'Account information such as name, email address, role, login status, tenant/organisation assignment, and authentication metadata.',
            'Employment records such as employee number, job title, department, reporting manager, employment status, hire date, work location, and job history.',
            'Contact information such as phone number, work email, and emergency contact details.',
            'Document metadata such as document title, type, upload date, expiry date, signature status, owner, and access permissions.',
            'Leave and attendance information such as leave balances, leave requests, approvals, rejections, check-in/check-out records, and attendance notes.',
            'Onboarding information such as assigned tasks, completion status, due dates, required reading, and form tracking.',
            'Audit and security data such as login events, IP address, user agent, timestamps, system actions, access logs, and permission changes.',
            'Support information such as messages, issue reports, screenshots, and correspondence sent to Ace support.',
          ]}
        />
      </Section>

      <Section title="5. Sensitive and Confidential HR Data">
        <p>
          HR systems may contain sensitive or confidential employment-related
          data. Ace applies role-based access control, tenant isolation, audit
          logging, and secure document handling to reduce unauthorised access.
        </p>
        <p>
          Client organisations are responsible for configuring access
          appropriately, assigning roles carefully, and ensuring that only
          authorised users are given access to employee records.
        </p>
      </Section>

      <Section title="6. How We Use Personal Data">
        <p>We process personal data to:</p>
        <BulletList
          items={[
            'Create and manage user accounts.',
            'Authenticate users and maintain secure sessions.',
            'Provide HRMIS features such as employee records, documents, leave, attendance, onboarding, dashboards, and compliance alerts.',
            'Enable platform hierarchy: Super Admin, Client Admin, Manager, and Employee access.',
            'Enforce tenant isolation and role-based permissions.',
            'Generate audit logs for security, compliance, and accountability.',
            'Provide customer support and troubleshoot technical issues.',
            'Maintain, secure, test, improve, and monitor the platform.',
            'Comply with applicable laws, regulatory obligations, lawful requests, and contractual commitments.',
          ]}
        />
      </Section>

      <Section title="7. Legal Bases for Processing">
        <p>
          Depending on the context, we may process personal data based on one or
          more lawful grounds, including:
        </p>
        <BulletList
          items={[
            'Performance of a contract with a client organisation or platform user.',
            'Compliance with legal, tax, employment, audit, or regulatory obligations.',
            'Legitimate interests such as platform security, service improvement, fraud prevention, business administration, and access control.',
            'Consent, where legally required or where no other lawful basis applies.',
            'The client organisation’s lawful basis for processing employee data where Ace acts as processor.',
          ]}
        />
      </Section>

      <Section title="8. How We Share Personal Data">
        <p>We may share personal data with:</p>
        <BulletList
          items={[
            'The client organisation that owns or administers the relevant workspace.',
            'Authorised users within the same organisation based on their role and permissions.',
            'Service providers that support hosting, infrastructure, storage, email, monitoring, analytics, security, and technical support.',
            'Professional advisers, auditors, insurers, or legal representatives where necessary.',
            'Regulators, courts, law enforcement, or public authorities where legally required.',
            'Successors or assigns in connection with a merger, acquisition, restructuring, or business transfer.',
          ]}
        />
        <p>
          We do not sell employee HR data. We do not permit unauthorised
          cross-tenant access between client organisations.
        </p>
      </Section>

      <Section title="9. International Transfers">
        <p>
          Ace may use cloud hosting and service providers that process data in
          countries outside the user’s country of residence. Where personal data
          is transferred internationally, we use appropriate safeguards such as
          contractual protections, access controls, data minimisation, and vendor
          security review.
        </p>
      </Section>

      <Section title="10. Data Security">
        <p>
          We use technical and organisational measures designed to protect
          personal data, including:
        </p>
        <BulletList
          items={[
            'Role-based access control.',
            'Tenant-level data isolation.',
            'Password hashing.',
            'JWT-based authentication.',
            'Secure document access restrictions.',
            'Audit logging for sensitive actions.',
            'Environment-based secrets management.',
            'HTTPS in production.',
            'Restricted CORS configuration.',
            'Database access controls.',
            'Soft-delete and retention-aware design.',
          ]}
        />
        <p>
          No system is completely secure. Users must protect their credentials,
          use strong passwords, and report suspected unauthorised access
          promptly.
        </p>
      </Section>

      <Section title="11. Data Retention">
        <p>
          We retain personal data for as long as necessary to provide the
          platform, comply with legal obligations, support HR compliance,
          resolve disputes, enforce agreements, maintain audit trails, and meet
          legitimate business needs.
        </p>
        <p>
          Client organisations control retention of most employee HR records.
          Deleted records may be soft-deleted first to preserve audit trails and
          may later be archived or permanently deleted according to applicable
          retention schedules.
        </p>
      </Section>

      <Section title="12. Your Privacy Rights">
        <p>
          Depending on applicable law and your location, you may have rights to:
        </p>
        <BulletList
          items={[
            'Request access to your personal data.',
            'Request correction of inaccurate or incomplete data.',
            'Request deletion of personal data where legally permitted.',
            'Object to or restrict certain processing.',
            'Request portability of personal data.',
            'Withdraw consent where processing is based on consent.',
            'Lodge a complaint with a competent data protection authority.',
          ]}
        />
        <p>
          If your data is controlled by your employer or organisation, we may
          direct your request to that organisation for handling.
        </p>
      </Section>

      <Section title="13. Client Organisation Responsibilities">
        <p>Client organisations using Ace are responsible for:</p>
        <BulletList
          items={[
            'Ensuring they have a lawful basis to process employee data.',
            'Providing employee notices and internal HR privacy information.',
            'Assigning user roles correctly.',
            'Maintaining accurate employee records.',
            'Complying with employment, tax, labour, data protection, and record retention requirements.',
            'Responding to employee privacy requests where they act as controller.',
            'Ensuring uploaded documents are lawful, necessary, accurate, and appropriately classified.',
          ]}
        />
      </Section>

      <Section title="14. Cookies and Similar Technologies">
        <p>
          Ace may use cookies, local storage, and similar technologies to keep
          users signed in, remember workspace preferences, improve security, and
          support platform functionality. Some of these technologies are
          necessary for authentication and cannot be disabled without affecting
          the service.
        </p>
      </Section>

      <Section title="15. Children’s Data">
        <p>
          Ace is designed for workplace HR administration and is not intended
          for use by children. Client organisations should not create accounts
          for users who are not legally eligible to use the platform unless a
          lawful employment or training basis exists and all applicable legal
          requirements are satisfied.
        </p>
      </Section>

      <Section title="16. Data Breach Handling">
        <p>
          If we become aware of a security incident affecting personal data, we
          will investigate, take reasonable containment steps, and notify
          affected client organisations or authorities where required by
          applicable law or contract.
        </p>
      </Section>

      <Section title="17. Updates to This Policy">
        <p>
          We may update this Privacy Policy from time to time. Material changes
          may be communicated through the platform, email, or other appropriate
          channels. Continued use of Ace after changes become effective means
          the updated policy applies.
        </p>
      </Section>

      <Section title="18. Contact Us">
        <p>
          For privacy questions or requests, contact us at{' '}
          <a
            className="font-semibold text-blue-700 hover:text-blue-900"
            href={`mailto:${COMPANY.contactEmail}`}
          >
            {COMPANY.contactEmail}
          </a>
          .
        </p>
      </Section>
    </LegalLayout>
  );
}

export function TermsOfService() {
  return (
    <LegalLayout
      title="Terms of Service"
      subtitle="These Terms of Service govern access to and use of the Ace HRMIS platform by client organisations, administrators, managers, employees, consultants, and authorised users."
    >
      <Section title="1. Agreement to Terms">
        <p>
          These Terms of Service form a legal agreement between you, your
          organisation where applicable, and {COMPANY.legalEntity}. By accessing
          or using Ace, you agree to comply with these Terms.
        </p>
        <p>
          If you are using Ace on behalf of an organisation, you represent that
          you are authorised to bind that organisation to these Terms.
        </p>
      </Section>

      <Section title="2. About Ace">
        <p>
          Ace is a consulting-led HRMIS platform that helps organisations manage
          employee records, documents, leave, attendance, onboarding, HR
          workflows, compliance alerts, and role-based HR administration.
        </p>
        <p>
          Ace is a software platform and operational tool. It does not replace
          legal, tax, employment, payroll, immigration, or professional HR advice
          unless such advice is separately provided under a signed consulting
          agreement.
        </p>
      </Section>

      <Section title="3. User Roles and Access Hierarchy">
        <p>Ace uses a role-based hierarchy:</p>
        <BulletList
          items={[
            'Super Admins manage the platform, onboard organisations, and create Client Admin accounts.',
            'Client Admins manage one organisation and may create, update, deactivate, or delete Manager and Employee accounts within that organisation.',
            'Managers may view permitted information for employees assigned to them and perform approved workflow actions.',
            'Employees may access their own self-service information, including profile, leave, documents, attendance, and onboarding tasks where enabled.',
          ]}
        />
        <p>
          Users must not attempt to access another organisation’s workspace or
          any employee record they are not authorised to view.
        </p>
      </Section>

      <Section title="4. Account Registration and Security">
        <p>Users are responsible for:</p>
        <BulletList
          items={[
            'Providing accurate account information.',
            'Keeping login credentials confidential.',
            'Using strong passwords.',
            'Not sharing accounts.',
            'Promptly reporting suspected unauthorised access.',
            'Logging out of shared or public devices.',
          ]}
        />
        <p>
          Ace may suspend or disable accounts where we reasonably suspect
          unauthorised access, misuse, breach of these Terms, or security risk.
        </p>
      </Section>

      <Section title="5. Client Organisation Responsibilities">
        <p>Client organisations are responsible for:</p>
        <BulletList
          items={[
            'Ensuring authorised users are correctly assigned.',
            'Maintaining accurate HR and employee records.',
            'Complying with employment, labour, tax, payroll, data protection, and record retention laws.',
            'Obtaining all required notices, consents, and lawful bases for processing employee data.',
            'Reviewing platform configuration and access permissions.',
            'Ensuring uploaded documents are lawful and appropriate.',
            'Backing up exported data where needed for internal business continuity.',
          ]}
        />
      </Section>

      <Section title="6. Acceptable Use">
        <p>You must not:</p>
        <BulletList
          items={[
            'Use Ace for unlawful, fraudulent, misleading, or harmful purposes.',
            'Access, copy, modify, or disclose data without authorisation.',
            'Bypass or attempt to bypass authentication, RBAC controls, tenant isolation, or security features.',
            'Upload malware, malicious scripts, or harmful files.',
            'Interfere with platform availability, performance, monitoring, or security.',
            'Reverse engineer, scrape, overload, or misuse the platform except where expressly permitted by law.',
            'Use Ace to store data that your organisation has no lawful right to process.',
          ]}
        />
      </Section>

      <Section title="7. Customer Data">
        <p>
          “Customer Data” means data submitted to Ace by or on behalf of a
          client organisation, including employee records, documents, workflow
          data, attendance records, leave records, onboarding data, and audit
          logs.
        </p>
        <p>
          As between Ace and the client organisation, the client organisation
          retains ownership of Customer Data. Ace receives a limited right to
          process Customer Data to provide, secure, maintain, support, and
          improve the platform and to comply with legal obligations.
        </p>
      </Section>

      <Section title="8. Confidentiality">
        <p>
          Users and organisations may access confidential HR, employment, and
          business information through Ace. Such information must be protected
          and used only for authorised business purposes.
        </p>
        <p>
          Users must not export, disclose, share, or misuse confidential
          information except as authorised by their organisation and applicable
          law.
        </p>
      </Section>

      <Section title="9. Documents and File Uploads">
        <p>
          Ace may allow authorised users to upload employment contracts,
          policies, tax forms, compliance records, certifications, and other HR
          documents. Users must ensure uploaded files are accurate, lawful,
          virus-free, and relevant to HR administration.
        </p>
        <p>
          Ace may restrict file types, file sizes, access rights, download
          rights, and retention periods for security and compliance reasons.
        </p>
      </Section>

      <Section title="10. Subscription, Fees, and Consulting Services">
        <p>
          Fees, billing cycles, consulting retainers, implementation packages,
          support levels, and service scope may be set out in a separate order
          form, proposal, invoice, or master services agreement.
        </p>
        <p>
          Unless otherwise agreed in writing, fees are non-refundable once a
          subscription period, implementation work, advisory work, or
          configuration service has commenced.
        </p>
      </Section>

      <Section title="11. Service Availability and Changes">
        <p>
          Ace aims to provide reliable service but does not guarantee
          uninterrupted availability. The platform may be unavailable due to
          maintenance, upgrades, hosting provider incidents, security events, or
          circumstances beyond our reasonable control.
        </p>
        <p>
          We may modify, improve, suspend, or discontinue features from time to
          time. Material changes affecting core functionality may be communicated
          where appropriate.
        </p>
      </Section>

      <Section title="12. Third-Party Services">
        <p>
          Ace may integrate with or rely on third-party services for hosting,
          storage, email, analytics, authentication, monitoring, payroll
          integrations, or support. Third-party services may be subject to their
          own terms and privacy policies.
        </p>
      </Section>

      <Section title="13. Intellectual Property">
        <p>
          Ace, including its software, design, workflows, documentation, source
          code, branding, platform architecture, templates, and related
          intellectual property, belongs to Ace or its licensors.
        </p>
        <p>
          These Terms do not transfer ownership of Ace intellectual property to
          users or client organisations.
        </p>
      </Section>

      <Section title="14. Feedback">
        <p>
          If users provide suggestions, improvement ideas, or feedback, Ace may
          use that feedback without restriction or obligation, provided we do
          not disclose confidential Customer Data.
        </p>
      </Section>

      <Section title="15. Suspension and Termination">
        <p>
          We may suspend or terminate access where there is non-payment, misuse,
          legal risk, security risk, breach of these Terms, unauthorised access,
          or a request from the client organisation that controls the workspace.
        </p>
        <p>
          On termination, access may be disabled. Data export, retention, and
          deletion will be handled according to the applicable agreement,
          retention policy, and legal requirements.
        </p>
      </Section>

      <Section title="16. Disclaimers">
        <p>
          Ace is provided on an “as is” and “as available” basis to the maximum
          extent permitted by law. We do not warrant that the platform will be
          error-free, uninterrupted, or suitable for every legal, HR, payroll, or
          compliance purpose.
        </p>
        <p>
          Client organisations remain responsible for verifying outputs,
          reports, calculations, compliance alerts, employee records, and
          administrative decisions.
        </p>
      </Section>

      <Section title="17. Limitation of Liability">
        <p>
          To the maximum extent permitted by law, Ace will not be liable for
          indirect, incidental, special, consequential, exemplary, or punitive
          damages, or for lost profits, lost revenue, lost goodwill, or loss of
          data arising from use of the platform.
        </p>
        <p>
          Any aggregate liability will be limited to the fees paid for the
          affected service during the period stated in the applicable commercial
          agreement, unless applicable law requires otherwise.
        </p>
      </Section>

      <Section title="18. Indemnity">
        <p>
          Client organisations agree to indemnify Ace against claims, losses,
          liabilities, damages, costs, and expenses arising from unlawful or
          unauthorised Customer Data, misuse of the platform, breach of these
          Terms, violation of applicable law, or user actions within their
          workspace.
        </p>
      </Section>

      <Section title="19. Governing Law and Disputes">
        <p>
          Unless a separate written agreement states otherwise, these Terms are
          governed by the laws of Kenya. Disputes should first be escalated in
          good faith between the parties before formal proceedings are
          commenced.
        </p>
      </Section>

      <Section title="20. Changes to These Terms">
        <p>
          We may update these Terms from time to time. Material changes may be
          communicated through the platform, email, or other appropriate
          channels. Continued use of Ace after changes become effective means
          the updated Terms apply.
        </p>
      </Section>

      <Section title="21. Contact">
        <p>
          For questions about these Terms, contact{' '}
          <a
            className="font-semibold text-blue-700 hover:text-blue-900"
            href={`mailto:${COMPANY.supportEmail}`}
          >
            {COMPANY.supportEmail}
          </a>
          .
        </p>
      </Section>
    </LegalLayout>
  );
}