document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('.site-header');
    if (header) {
        window.addEventListener('scroll', () => {
            header.classList.toggle('is-scrolled', window.scrollY > 10);
        });
    }

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach((link) => {
        link.addEventListener('click', (event) => {
            const targetId = link.getAttribute('href').slice(1);
            const target = document.getElementById(targetId);
            if (target) {
                event.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Reveal on scroll animations
    const revealItems = document.querySelectorAll('.reveal');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.16 });
    revealItems.forEach((item) => observer.observe(item));

    // Highlight selected vote option
    const voteInputs = document.querySelectorAll('.vote-option input[type="radio"]');
    voteInputs.forEach((input) => {
        input.addEventListener('change', () => {
            const groupName = input.name;
            document.querySelectorAll(`input[name="${groupName}"]`).forEach((radio) => {
                radio.closest('.vote-option')?.classList.remove('selected');
            });
            input.closest('.vote-option')?.classList.add('selected');
        });
    });
});
