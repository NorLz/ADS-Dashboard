let currentPageIndex = 0;

function navigate(event, index) {
    event.preventDefault();

    if (index !== currentPageIndex) {
        // Update container position by translating it horizontally
        const container = document.querySelector('.container');
        container.style.transform = `translateX(-${index * 100}vw)`; // Adjust for full-width container scroll

        // Update button states
        const buttons = document.querySelectorAll('.nav-button');
        buttons.forEach(button => {
            button.classList.remove('bg-white', 'opacity-100'); // Remove active styles
            button.classList.add('bg-[#F2F2F2]', 'opacity-50'); // Restore default styles
        });

        // Add active styles to the clicked button
        buttons[index].classList.add('bg-white', 'opacity-100');
        buttons[index].classList.remove('bg-[#F2F2F2]', 'opacity-50');

        // Update current page index
        currentPageIndex = index;
    }

    // Show or hide the navigation buttons based on the current page index
    const navButtons = document.getElementById('nav-buttons');
    if (navButtons) {
        if (index === 0) {
            // Hide navigation buttons when on the home page (page 0)
            navButtons.classList.add('hidden');
        } else {
            // Show navigation buttons on other pages
            navButtons.classList.remove('hidden');
        }
    }
}

function showNavButtons() {
    // Remove the 'hidden' class from the navigation buttons (can be called to show buttons explicitly)
    const navButtons = document.getElementById('nav-buttons');
    if (navButtons) {
        navButtons.classList.remove('hidden');
    }
}

  // Back to Top Button
  const backToTopBtn = document.getElementById('backToTopBtn');

  window.onscroll = function() {
    if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
      backToTopBtn.style.opacity = '1';
    } else {
      backToTopBtn.style.opacity = '0';
    }
  };

  backToTopBtn.onclick = function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
