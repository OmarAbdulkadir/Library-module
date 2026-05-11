/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class LibraryDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            activeTab: "dashboard",
            stats: { books: 0, members: 0, borrows: 0, pendingBookings: 0, rooms: 0, overdueCount: 0 },
            books: [],
            members: [],
            borrows: [],
            rooms: [],
            bookings: [],
            schedule: {},
            scheduleDate: "",
            scheduleOffset: 0,
            loading: true,
            bookFilter: "all",
            categoryFilter: "all",
            bookingFilter: "all",
            searchBook: "",
            announcement: "",
            showAnnouncement: false,
            currentTime: "",
            libraryOpen: false,
            mostBorrowedBook: null,
            userName: "",
            topBooks: [],
            topMembers: [],
            myReservations: [],
            myBookings: [],
            notificationCount: 0,
            showBookingModal: false,
            modalRoomId: null,
            modalSlot: null,
            modalDate: "",
            modalGroupSize: 3,
            modalLanguage: "en",
            modalNeedsComputer: false,
            ambientMood: "quiet",
            isAdmin: false,
            isStaff: false,
            isPortal: false,
        });

        this._clockInterval = null;

        onWillStart(async () => {
            await this.detectUserRole();
            await this.loadAll();
            try {
                const resp = await fetch("/web/session/get_session_info", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }) });
                const data = await resp.json();
                this.state.userName = data.result.name || "";
            } catch(e) {}
        });

        onMounted(() => {
            this._updateClock();
            this._clockInterval = setInterval(() => this._updateClock(), 1000);
            this._initScrollAnimations();
            if (this.state.isPortal) {
                document.body.classList.add('library_student_mode');
            }
        });

        onWillUnmount(() => {
            if (this._clockInterval) clearInterval(this._clockInterval);
        });
    }

    async detectUserRole() {
        try {
            await this.orm.searchRead("ir.config_parameter",
                [["key", "=", "library.show_warning"]], ["key"], { limit: 1 });
            this.state.isAdmin = true;
            this.state.isStaff = true;
            this.state.isPortal = false;
            return;
        } catch(e) {}
        try {
            await this.orm.call("library.member", "check_access_rights", ["write"], { raise_exception: true });
            this.state.isAdmin = false;
            this.state.isStaff = true;
            this.state.isPortal = false;
        } catch(e) {
            this.state.isAdmin = false;
            this.state.isStaff = false;
            this.state.isPortal = true;
        }
    }

    _updateClock() {
        const now = new Date();
        const hours = now.getHours();
        const minutes = String(now.getMinutes()).padStart(2, "0");
        const seconds = String(now.getSeconds()).padStart(2, "0");
        const ampm = hours >= 12 ? "PM" : "AM";
        const h12 = hours % 12 || 12;
        this.state.currentTime = `${h12}:${minutes}:${seconds} ${ampm}`;
        this.state.libraryOpen = hours >= 8 && hours < 22;
    }

    _initScrollAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("lib-visible");
                }
            });
        }, { threshold: 0.1 });
        setTimeout(() => {
            document.querySelectorAll(".lib-animate").forEach(el => observer.observe(el));
        }, 300);
    }

    _computeAmbientMood() {
        const rooms = this.state.rooms;
        if (!rooms.length) { this.state.ambientMood = "quiet"; return; }
        const totalCapacity = rooms.reduce((s, r) => s + r.capacity, 0);
        const totalOccupancy = rooms.reduce((s, r) => s + r.current_occupancy, 0);
        const ratio = totalCapacity > 0 ? totalOccupancy / totalCapacity : 0;
        if (ratio === 0) this.state.ambientMood = "quiet";
        else if (ratio < 0.4) this.state.ambientMood = "moderate";
        else if (ratio < 0.75) this.state.ambientMood = "busy";
        else this.state.ambientMood = "full";
    }

    _computeMostBorrowedBook() {
        const counts = {};
        this.state.borrows.forEach(b => {
            const name = b.book_id[1];
            counts[name] = (counts[name] || 0) + 1;
        });
        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        this.state.mostBorrowedBook = sorted.length ? { name: sorted[0][0], count: sorted[0][1] } : null;
    }

    async loadAll() {
        this.state.loading = true;
        try {
            await Promise.all([
                this.loadStats(),
                this.loadBooks(),
                this.loadMembers(),
                this.loadMyProfile(),
                this.loadBorrows(),
                this.loadRooms(),
                this.loadBookings(),
                this.loadSettings(),
                this.loadSchedule(),
            ]);
            this._computeAmbientMood();
            this._computeMostBorrowedBook();
        } finally {
            this.state.loading = false;
        }
    }

    async loadStats() {
        try {
            const [books, members, borrows, rooms, pending, overdue] = await Promise.all([
                this.orm.searchCount("library.book", []),
                this.orm.searchCount("library.member", []),
                this.orm.searchCount("library.borrow", [["state", "=", "borrowed"]]),
                this.orm.searchCount("library.room", []),
                this.orm.searchCount("library.room.booking", [["state", "=", "pending"]]),
                this.orm.searchCount("library.borrow", [["is_overdue", "=", true]]),
            ]);
            this.state.stats = { books, members, borrows, rooms, pendingBookings: pending, overdueCount: overdue };
            if (!this.state.isPortal) this.state.notificationCount = pending + overdue;
            const topBooks = await this.orm.searchRead("library.book", [],
                ["name", "borrow_count"], { order: "borrow_count desc", limit: 5 });
            this.state.topBooks = topBooks;
            const topMembers = await this.orm.searchRead("library.member", [],
                ["name", "total_borrows"], { order: "total_borrows desc", limit: 5 });
            this.state.topMembers = topMembers;
        } catch(e) {
            const [books, rooms, pending] = await Promise.all([
                this.orm.searchCount("library.book", []),
                this.orm.searchCount("library.room", []),
                this.orm.searchCount("library.room.booking", [["state", "=", "pending"]]),
            ]);
            this.state.stats = { books, members: 0, borrows: 0, rooms, pendingBookings: pending, overdueCount: 0 };
        }
    }
    async loadBooks() {
        this.state.books = await this.orm.searchRead("library.book", [],
            ["name", "author", "book_type", "state", "available_copies", "total_copies", "download_url", "category", "edition"]);
    }
    async loadMembers() {
        if (this.state.isPortal) return;
        try {
            this.state.members = await this.orm.searchRead("library.member", [],
                ["name", "student_id", "email", "borrow_limit", "active_borrows", "streak", "state", "has_overdue"]);
        } catch(e) {}
    }
    async loadMyProfile() {
        if (!this.state.isPortal) return;
        try {
            const resp = await fetch("/web/session/get_session_info", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} })
            });
            const data = await resp.json();
            const uid = data.result.uid;
            // Load my borrows
            this.state.borrows = await this.orm.searchRead("library.borrow", [],
                ["name", "book_id", "borrow_date", "due_date", "return_date", "state", "fine_amount", "is_overdue"],
                { order: "id desc", limit: 50 });
            // Load my reservations
            this.state.myReservations = await this.orm.searchRead("library.reservation", [],
                ["book_id", "reservation_date", "expiry_date", "state"],
                { order: "id desc", limit: 20 });
            // Load my bookings
            this.state.myBookings = await this.orm.searchRead("library.room.booking", [],
                ["room_id", "booking_date", "time_slot", "state"],
                { order: "id desc", limit: 20 });
            // Calculate notifications
            const pendingBorrows = this.state.borrows.filter(b => b.state === "pending").length;
            const notifiedReservations = this.state.myReservations.filter(r => r.state === "notified").length;
            this.state.notificationCount = pendingBorrows + notifiedReservations;
        } catch(e) {}
    }

    async loadBorrows() {
        if (this.state.isPortal) return;
        try {
            this.state.borrows = await this.orm.searchRead("library.borrow", [],
                ["name", "member_id", "book_id", "borrow_date", "due_date", "state", "fine_amount", "is_overdue"],
                { order: "id desc", limit: 50 });
        } catch(e) {}
    }

    async loadRooms() {
        this.state.rooms = await this.orm.searchRead("library.room", [],
            ["name", "capacity", "current_occupancy", "occupancy_percent", "has_computers",
             "computer_count", "computers_available", "state", "is_crowded"]);
    }

    async loadBookings() {
        try {
            const domain = this.state.bookingFilter === "all" ? [] : [["state", "=", this.state.bookingFilter]];
            this.state.bookings = await this.orm.searchRead("library.room.booking", domain,
                ["name", "member_id", "room_id", "start_time", "end_time", "duration_hours", "state", "qr_code"],
                { order: "id desc" });
        } catch(e) {}
    }

    async loadSchedule() {
        const today = new Date();
        today.setDate(today.getDate() + (this.state.scheduleOffset || 0));
        const dateStr = today.toISOString().split('T')[0];
        this.state.scheduleDate = dateStr;
        try {
            const bookings = await this.orm.searchRead(
                "library.room.booking",
                [["booking_date", "=", dateStr], ["state", "in", ["pending", "approved", "active"]]],
                ["room_id", "time_slot", "member_id", "state", "group_size"]
            );
            const grid = {};
            bookings.forEach(b => {
                const key = b.room_id[0] + "-" + b.time_slot;
                grid[key] = {
                    state: b.state,
                    member: b.member_id ? b.member_id[1] : "",
                    group_size: b.group_size,
                    id: b.id,
                };
            });
            this.state.schedule = grid;
        } catch(e) {
            this.state.schedule = {};
        }
    }

    async loadSettings() {
        try {
            const params = await this.orm.searchRead("ir.config_parameter",
                [["key", "in", ["library.show_warning", "library.warning_message"]]],
                ["key", "value"]);
            const showWarning = params.find(p => p.key === "library.show_warning");
            const message = params.find(p => p.key === "library.warning_message");
            this.state.showAnnouncement = showWarning?.value === "True";
            this.state.announcement = message?.value || "";
        } catch (e) {
            this.state.showAnnouncement = false;
            this.state.announcement = "";
        }
    }

    setTab(tab) {
        this.state.activeTab = tab;
        if (tab === "profile" || tab === "borrows") {
            this.state.notificationCount = 0;
        }
        setTimeout(() => this._initScrollAnimations(), 100);
    }

    setBookFilter(filter) { this.state.bookFilter = filter; }

    async setBookingFilter(filter) {
        this.state.bookingFilter = filter;
        await this.loadBookings();
    }

    get filteredBooks() {
        let books = this.state.books;
        if (this.state.bookFilter !== "all") {
            books = books.filter(b => b.book_type === this.state.bookFilter);
        }
        if (this.state.categoryFilter !== "all") {
            books = books.filter(b => b.category && b.category.toLowerCase() === this.state.categoryFilter.toLowerCase());
        }
        if (this.state.searchBook) {
            const q = this.state.searchBook.toLowerCase();
            books = books.filter(b => b.name.toLowerCase().includes(q) || b.author.toLowerCase().includes(q));
        }
        return books;
    }
    get bookCategories() {
        const cats = this.state.books.map(b => b.category).filter(c => c);
        return ["all", ...new Set(cats)];
    }

    getRoomLight(room) {
        if (room.capacity === 0) return "grey";
        const ratio = room.current_occupancy / room.capacity;
        if (ratio < 0.6) return "green";
        if (ratio < 0.85) return "yellow";
        return "red";
    }

    getRoomOccupancyPercent(room) {
        if (room.capacity === 0) return 0;
        return Math.min(100, Math.round((room.current_occupancy / room.capacity) * 100));
    }

    async updateOccupancy(roomId, delta) {
        const room = this.state.rooms.find(r => r.id === roomId);
        if (!room) return;
        const newOcc = room.current_occupancy + delta;
        if (newOcc < 0 || newOcc > room.capacity) return;
        await this.orm.call("library.room", "write", [[roomId], {
            current_occupancy: newOcc,
            occupancy_percent: (newOcc / room.capacity) * 100,
            is_crowded: (newOcc / room.capacity) >= 0.8,
        }]);
        await this.loadRooms();
        this._computeAmbientMood();
        this.notification.add("Occupancy updated!", { type: "success" });
    }

    async approveBooking(id) {
        await this.orm.call("library.room.booking", "action_approve", [[id]]);
        await this.loadBookings();
        await this.loadStats();
        await this.loadRooms();
        await this.loadSchedule();
        this._computeAmbientMood();
        this.notification.add("Booking approved!", { type: "success" });
    }

    async rejectBooking(id) {
        await this.orm.call("library.room.booking", "action_reject", [[id]]);
        await this.loadBookings();
        await this.loadStats();
        await this.loadSchedule();
        this.notification.add("Booking rejected!", { type: "warning" });
    }

    async checkinBooking(id) {
        await this.orm.call("library.room.booking", "action_checkin", [[id]]);
        await this.loadBookings();
        await this.loadRooms();
        await this.loadSchedule();
        this._computeAmbientMood();
        this.notification.add("Checked in!", { type: "success" });
    }

    async checkoutBooking(id) {
        await this.orm.call("library.room.booking", "action_checkout", [[id]]);
        await this.loadBookings();
        await this.loadRooms();
        await this.loadSchedule();
        this._computeAmbientMood();
        this.notification.add("Checked out!", { type: "success" });
    }

    async returnBook(id) {
        await this.orm.call("library.borrow", "action_return", [[id]]);
        await this.loadBorrows();
        await this.loadStats();
        await this.loadBooks();
        this._computeMostBorrowedBook();
        this.notification.add("Book returned!", { type: "success" });
    }
    async approveBorrow(id) {
        try {
            await this.orm.call("library.borrow", "action_approve", [[id]]);
            await this.loadBorrows();
            await this.loadStats();
            await this.loadBooks();
            this.notification.add("Borrow approved!", { type: "success" });
        } catch(e) {
            this.notification.add("Error: " + e.message, { type: "danger" });
        }
    }
    async rejectBorrow(id) {
        try {
            await this.orm.call("library.borrow", "action_reject", [[id]]);
            await this.loadBorrows();
            await this.loadStats();
            this.notification.add("Borrow rejected.", { type: "warning" });
        } catch(e) {
            this.notification.add("Error: " + e.message, { type: "danger" });
        }
    }

    async saveSetting(key, value) {
        await this.orm.call("ir.config_parameter", "set_param", [key, String(value)]);
        await this.loadSettings();
        this.notification.add("Settings saved!", { type: "success" });
    }

    async changeScheduleDay(delta) {
        this.state.scheduleOffset = (this.state.scheduleOffset || 0) + delta;
        if (this.state.scheduleOffset < 0) this.state.scheduleOffset = 0;
        await this.loadSchedule();
    }

    bookSlot(roomId, slot) {
        this.state.modalRoomId = roomId;
        this.state.modalSlot = slot;
        this.state.modalDate = this.state.scheduleDate;
        this.state.modalGroupSize = 3;
        this.state.showBookingModal = true;
    }
    async submitBooking() {
        try {
            const members = await this.orm.searchRead("library.member", [], ["id", "name"], { limit: 1 });
            if (!members.length) {
                this.notification.add("No member account found.", { type: "danger" });
                return;
            }
            await this.orm.create("library.room.booking", [{
                room_id: this.state.modalRoomId,
                time_slot: this.state.modalSlot,
                booking_date: this.state.modalDate,
                member_id: members[0].id,
                group_size: this.state.modalGroupSize,
                language: this.state.modalLanguage,
                needs_computer: this.state.modalNeedsComputer,
            }]);
            this.state.showBookingModal = false;
            this.notification.add("Room booked! Waiting for staff approval.", { type: "success" });
            await this.loadSchedule();
        } catch(e) {
            this.notification.add("Error: " + e.message, { type: "danger" });
        }
    }

    openRecord(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openList(model) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
    async reserveBook(bookId, bookName) {
        try {
            const members = await this.orm.searchRead("library.member",
                [], ["id", "name"], { limit: 10 });
            if (!members.length) {
                this.notification.add("No member account found. Please contact staff.", { type: "danger" });
                return;
            }
            const member = members[0];
            await this.orm.create("library.reservation", [{
                book_id: bookId,
                member_id: member.id,
            }]);
            this.notification.add("Reserved! You will be notified when the book is available.", { type: "success" });
            await this.loadAll();
        } catch(e) {
            this.notification.add("Error: " + e.message, { type: "danger" });
        }
    }
    async requestBorrow(bookId) {
        try {
            const members = await this.orm.searchRead("library.member",
                [], ["id", "name"], { limit: 10 });
            if (!members.length) {
                this.notification.add("No member account found. Please contact staff.", { type: "danger" });
                return;
            }
            const member = members[0];
            const today = new Date().toISOString().split("T")[0];
            await this.orm.create("library.borrow", [{
                book_id: bookId,
                member_id: member.id,
                borrow_date: today,
                due_date: today,
                state: "pending",
            }]);
            this.notification.add("Borrow request sent! Staff will review it.", { type: "success" });
            await this.loadAll();
        } catch(e) {
            this.notification.add("Error sending request: " + e.message, { type: "danger" });
        }
    }
}
LibraryDashboard.template = "library.Dashboard";
registry.category("actions").add("library.dashboard", LibraryDashboard);
