/* ============================================
   ORIGIN — Landing Page Scripts
   ============================================ */

(function () {
  'use strict';

  // --- Scroll Reveal ---
  function initReveal() {
    var reveals = document.querySelectorAll('.reveal');

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.15,
      rootMargin: '0px 0px -50px 0px'
    });

    reveals.forEach(function (el) {
      observer.observe(el);
    });
  }

  // --- Navigation scroll state ---
  function initNav() {
    var nav = document.getElementById('nav');
    var scrollThreshold = 80;

    function onScroll() {
      if (window.scrollY > scrollThreshold) {
        nav.classList.add('nav--scrolled');
      } else {
        nav.classList.remove('nav--scrolled');
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // --- Smooth scroll for anchor links ---
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        var targetId = this.getAttribute('href');
        if (targetId === '#') return;

        var target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
  }

  // --- Waitlist Form ---
  function initWaitlistForm() {
    var form = document.getElementById('waitlist-form');
    var success = document.getElementById('waitlist-success');

    if (!form || !success) return;

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var emailInput = document.getElementById('waitlist-email');
      var email = emailInput.value.trim();

      if (!email) return;

      // Store email (front-end only — connect to Klaviyo/Mailchimp later)
      var waitlist = JSON.parse(localStorage.getItem('origin_waitlist') || '[]');
      if (waitlist.indexOf(email) === -1) {
        waitlist.push(email);
        localStorage.setItem('origin_waitlist', JSON.stringify(waitlist));
      }

      // Show success state
      form.style.display = 'none';
      success.classList.add('is-visible');
    });
  }

  // --- Parallax orbs on mouse move (subtle, non-hero only) ---
  function initParallax() {
    // Exclude hero orb since it has its own CSS animation with transform
    var orbs = document.querySelectorAll('.intro__orb, .ritual__orb');

    if (window.matchMedia('(pointer: fine)').matches) {
      document.addEventListener('mousemove', function (e) {
        var x = (e.clientX / window.innerWidth - 0.5) * 2;
        var y = (e.clientY / window.innerHeight - 0.5) * 2;

        orbs.forEach(function (orb) {
          var rect = orb.getBoundingClientRect();
          var inView = rect.top < window.innerHeight && rect.bottom > 0;

          if (inView) {
            orb.style.transform =
              'translate(' +
              (x * 15) + 'px, ' +
              (y * 15) + 'px)';
          }
        });
      });
    }
  }

  // --- Init ---
  document.addEventListener('DOMContentLoaded', function () {
    initNav();
    initReveal();
    initSmoothScroll();
    initWaitlistForm();
    initParallax();
  });
})();
