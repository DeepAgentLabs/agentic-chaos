// Main JavaScript for agentic-chaos website

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && document.querySelector(href)) {
                e.preventDefault();
                document.querySelector(href).scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // Add animation to elements on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.6s ease-out';
                observer.unobserve(entry.target);
            }
        });
    });

    document.querySelectorAll('.feature, .fault-card, .stat, .blog-card').forEach(el => {
        observer.observe(el);
    });
});

// Track page analytics if configured
window.addEventListener('load', function() {
    // Custom analytics can be added here
    console.log('agentic-chaos website loaded');
});
