# WashBot Specification

## 1. Product Summary

WashBot is a Telegram-first booking and automation bot for local car washes. The product helps car wash customers book available time slots, select services, receive reminders, and get promotional offers. For car wash owners, WashBot acts as a lightweight digital administrator that manages bookings, services, notifications, customer history, and basic operational settings.

The product is designed as a sellable automation solution for car wash businesses. The long-term goal is to package the bot so that after sale and setup, the owner or administrator can operate it independently without ongoing manual support from the developer.

## 2. Core Idea

Car wash businesses often depend on phone calls, messengers, and manual administrator work to manage appointments. This causes missed bookings, double-booking, unclear availability, and poor customer retention.

WashBot solves this by giving each car wash a bot-based booking system where customers can:

- see available time slots;
- choose services;
- book a visit;
- receive reminders;
- receive offers and return-visit notifications.

Car wash staff can:

- manage working hours;
- manage services and prices;
- confirm or cancel bookings;
- see upcoming appointments;
- send promotions;
- reduce repetitive administrator work.

## 3. Target Users

### 3.1 Car Wash Customers

People who want to wash their car and prefer booking through a messenger instead of calling.

Primary needs:

- quickly find free time;
- understand available services and prices;
- book without waiting for administrator response;
- receive reminders;
- cancel or reschedule if needed.

### 3.2 Car Wash Owner

The person who buys or subscribes to WashBot.

Primary needs:

- reduce administrator workload;
- avoid missed bookings;
- increase repeat visits;
- see customer and booking data;
- manage the bot without technical help;
- get a product that works after setup.

### 3.3 Car Wash Administrator

The daily operator who manages bookings.

Primary needs:

- see all current bookings;
- change appointment status;
- manually add bookings if a customer calls;
- block time slots;
- communicate with customers through notifications.

### 3.4 Product Owner / Developer

The seller and initial maintainer of WashBot.

Primary needs:

- make the product repeatable for multiple car washes;
- reduce custom development per client;
- automate onboarding and configuration;
- minimize support after sale.

## 4. Supported Platforms

### 4.1 Telegram

Telegram is the main launch platform.

Reasons:

- users already understand bots;
- strong bot API;
- easy notifications;
- easy sharing through links and QR codes;
- suitable for local business workflows.

### 4.2 MAX

MAX support should be researched as a future platform.

Open questions:

- whether MAX provides a public bot API;
- what message types and buttons are supported;
- whether payments, deep links, and notifications are available;
- whether business accounts or integrations are supported.

MVP should not depend on MAX. The architecture should keep messaging logic separate so MAX can be added later if the platform API allows it.

## 5. MVP Scope

The MVP should prove that one car wash can operate booking through Telegram without manual developer involvement during daily use.

### 5.1 Customer Features

- Open bot from link or QR code.
- Select car wash branch if several branches exist.
- View service categories.
- Select one or several services.
- See service duration and price.
- Choose date.
- See available time slots.
- Book an appointment.
- Enter customer name.
- Enter phone number.
- Enter car model or license plate if required.
- Receive booking confirmation.
- Receive reminder before the visit.
- Cancel booking from bot.
- View active booking.

### 5.2 Administrator Features

- View today's bookings.
- View bookings by date.
- Confirm booking.
- Cancel booking.
- Mark booking as completed.
- Mark booking as no-show.
- Add manual booking.
- Block time slot.
- Edit booking comment.
- Receive notification about new booking.

### 5.3 Owner Features

- Configure car wash name.
- Configure branch address.
- Configure working hours.
- Configure service list.
- Configure prices.
- Configure service duration.
- Configure administrator Telegram accounts.
- Configure reminder timing.
- Enable or disable promotions.
- Export bookings and customers.

### 5.4 Promotion Features

- Send return-visit reminder after a configured number of days.
- Send simple promotional message to customer base.
- Segment customers by last visit date.
- Segment customers by service used.
- Respect opt-out from marketing messages.

## 6. Post-MVP Features

- Online payment or deposit before booking.
- Loyalty program.
- Bonus points.
- Customer ratings after visit.
- Reviews and feedback collection.
- Multiple employees or wash bays.
- Load-based scheduling by bay availability.
- Analytics dashboard.
- Web admin panel.
- Integration with CRM.
- Integration with accounting.
- Integration with maps.
- Multi-platform support: Telegram and MAX.
- White-label mode for each car wash.

## 7. Booking Logic

### 7.1 Time Slots

Time slots are generated from:

- working hours;
- service duration;
- existing bookings;
- blocked time;
- number of available wash bays.

Example:

- working hours: 09:00-21:00;
- slot step: 30 minutes;
- selected service duration: 60 minutes;
- wash bays: 2.

The bot should show only slots where the selected service can fit and where capacity is available.

### 7.2 Booking Statuses

Booking statuses:

- `pending`;
- `confirmed`;
- `cancelled_by_customer`;
- `cancelled_by_admin`;
- `completed`;
- `no_show`.

For MVP, bookings can be auto-confirmed or manually confirmed depending on owner settings.

### 7.3 Cancellation Rules

The owner should be able to configure:

- whether customers can cancel;
- minimum cancellation time before visit;
- administrator notification on cancellation.

## 8. Payments

Payments are optional for MVP.

### 8.1 Recommended MVP Payment Model

The first version should allow booking without online payment. This reduces launch complexity and makes it easier to sell to local car washes.

### 8.2 Future Payment Options

Possible payment flows:

- customer pays full amount online;
- customer pays deposit online;
- customer pays at the car wash;
- car wash owner pays monthly subscription for using WashBot;
- car wash owner buys one-time setup plus optional support package.

### 8.3 Who Pays

Primary business model:

- the car wash owner pays for the bot;
- customers use the bot for free.

Possible pricing:

- setup fee;
- monthly subscription;
- separate paid support;
- separate customization fee;
- separate hosting fee if hosted by developer.

## 9. Database

### 9.1 Recommended Database

PostgreSQL is recommended for production.

Reasons:

- reliable relational data model;
- good support for bookings and schedules;
- easy backups;
- works well with future analytics;
- can support multiple car washes in one system.

SQLite can be used only for prototype or local development.

### 9.2 Core Tables

Recommended entities:

- `car_washes`;
- `branches`;
- `users`;
- `customers`;
- `admins`;
- `services`;
- `service_categories`;
- `wash_bays`;
- `working_hours`;
- `blocked_slots`;
- `bookings`;
- `booking_services`;
- `notifications`;
- `promotions`;
- `payments`;
- `audit_logs`;
- `settings`.

### 9.3 Multi-Tenant Design

The system should support multiple car washes from the beginning.

Every business entity should belong to `car_wash_id`.

This allows selling the same product to several owners without creating a separate codebase for each client.

## 10. Admin Interaction

### 10.1 Telegram Admin Mode

MVP can use Telegram admin commands and inline buttons.

Examples:

- `Today's bookings`;
- `Tomorrow`;
- `Choose date`;
- `Services`;
- `Settings`;
- `Block slot`;
- `Add booking`.

This avoids building a web dashboard too early.

### 10.2 Web Admin Panel

A web admin panel is recommended after MVP if owners need easier configuration.

The panel should include:

- calendar view;
- service editor;
- working hours editor;
- customer list;
- promotion sender;
- export tools;
- subscription and billing state.

## 11. Customer Flow

1. Customer opens bot.
2. Bot shows car wash greeting and main actions.
3. Customer selects `Book a wash`.
4. Customer selects service.
5. Bot shows price and estimated duration.
6. Customer selects date.
7. Bot shows available time slots.
8. Customer selects time.
9. Bot asks for phone number.
10. Bot asks for car information if enabled.
11. Bot creates booking.
12. Customer receives confirmation.
13. Administrator receives notification.
14. Bot sends reminder before visit.
15. After visit, bot can send feedback or return reminder.

## 12. Owner Onboarding Flow

1. Owner buys or subscribes to WashBot.
2. Owner fills setup form.
3. Required setup data:
   - car wash name;
   - address;
   - working hours;
   - services;
   - prices;
   - service duration;
   - number of wash bays;
   - administrator Telegram usernames or IDs;
   - reminder settings.
4. Bot instance or tenant is configured.
5. Owner receives bot link and QR code.
6. Owner tests booking flow.
7. Bot goes live.

## 13. Reducing Developer Support After Sale

The product should be built so the owner can operate it independently.

Required mechanisms:

- owner/admin settings inside bot or admin panel;
- documentation for owner;
- onboarding checklist;
- automatic backups;
- clear error messages;
- admin notifications for failed actions;
- subscription/payment automation;
- hosting monitoring;
- ability to export data;
- separate paid support plan.

To fully remove developer involvement, the best model is:

- hosted SaaS with automated billing;
- self-service settings;
- standard feature set;
- no custom code per client;
- support handled through documentation or paid support package.

If a one-time sale is used, the owner must be responsible for hosting, domain, server, database backups, bot token safety, and future updates. This is harder for non-technical clients.

## 14. Recommended Business Model

Recommended model:

- setup fee for initial configuration;
- monthly subscription for hosting, updates, and system availability;
- paid customizations separately;
- paid support separately after included onboarding period.

This model is better than a one-time sale because the bot requires:

- hosting;
- database backups;
- Telegram API maintenance;
- bug fixes;
- occasional updates;
- monitoring.

Possible packages:

- Basic: booking, services, reminders.
- Standard: booking, reminders, customer base, promotions.
- Pro: multi-branch, analytics, web admin panel, loyalty, integrations.

## 15. Technical Architecture

Recommended architecture:

- backend application;
- Telegram bot adapter;
- future MAX bot adapter;
- PostgreSQL database;
- background jobs for reminders and promotions;
- admin interface through Telegram first;
- optional web admin panel later;
- deployment on VPS or managed hosting.

### 15.1 Separation of Concerns

The application should separate:

- business logic;
- database layer;
- Telegram-specific message handling;
- notification scheduler;
- payment provider integration;
- admin UI;
- customer UI.

This makes it easier to add MAX later.

## 16. Notifications

Notification types:

- booking confirmation;
- new booking to admin;
- booking cancellation;
- reminder before visit;
- return-visit reminder;
- promotion message;
- feedback request;
- system warning to owner.

Notification jobs should be stored in the database and processed by a background worker.

## 17. Legal And Privacy Notes

The system stores customer personal data, including phone numbers and car information.

Required:

- privacy policy;
- user consent for personal data processing;
- marketing opt-out;
- secure storage of bot tokens;
- restricted admin access;
- database backups;
- ability to delete customer data on request.

For Russia, personal data requirements should be checked before production launch.

## 18. Success Criteria

MVP is successful if:

- customer can book a car wash visit without calling;
- administrator receives and manages bookings;
- owner can edit services and working hours;
- reminders are sent automatically;
- no double-booking occurs;
- booking data is stored reliably;
- one car wash can operate the system for at least two weeks without developer intervention.

## 19. Open Questions

- Which city is the first launch market?
- Will the first client have one branch or multiple branches?
- Should bookings be auto-confirmed or manually confirmed?
- How many wash bays should the scheduling model support?
- Does the owner need online payments at launch?
- Is a web admin panel required for MVP, or is Telegram admin mode enough?
- Should each car wash have a separate bot, or should one bot support multiple car washes?
- What stack will be used for backend development?
- Who will host the product after sale?
- Is MAX integration required for first release or only later?

## 20. MVP Development Milestones

### Milestone 1: Foundation

- project setup;
- database schema;
- Telegram bot connection;
- basic customer identity;
- car wash and branch configuration.

### Milestone 2: Booking

- service selection;
- date selection;
- available time slots;
- booking creation;
- booking cancellation;
- admin notification.

### Milestone 3: Admin Operations

- admin booking list;
- booking status changes;
- manual booking;
- blocked slots;
- service management.

### Milestone 4: Notifications

- confirmation messages;
- reminder jobs;
- cancellation notifications;
- return-visit reminders.

### Milestone 5: Productization

- owner onboarding checklist;
- export tools;
- backup strategy;
- deployment guide;
- pricing/package documentation;
- support boundaries.

